// calibrado para ruedas chiquitas

// --- Pines de motores 
static int PinIN1 = 6; 
static int PinIN2 = 3;
static int PinIN3 = 9;
static int PinIN4 = 11;

// --- Sensores: 4, centrados. El ultra izquierdo (A4) se saco porque no andaba.
// De izquierda a derecha: extremo izq, medio izq, medio der, extremo der.
static int Pin_sensor_eizq = A3;
static int Pin_sensor_mizq = A2;
static int Pin_sensor_mder = A1;
static int Pin_sensor_eder = A0;
 
// --- Pines que vienen de la Raspberry (4 cables + GND)
// Modo normal:    13 = semaforo verde (arranca), 12 = PARE (frena 5 s), 7 = muñeco (frena 10 s)
// Modo felicidad: 12 = motor izquierdo, 13 = motor derecho, 7 = reversa (WASD desde la compu)
static int PinSemaforo = 13;  // GPIO16 de la Raspberry
bool semaforo_verde = 0, arranque=0;
static int PinPare = 12;      // GPIO26 de la Raspberry
bool senialpare=0, stopflag=0;
unsigned long tiempo_actual = 0, tiempo_inicio=0, tiempo_pasado=0;
static int PinMuneco = 7;     // GPIO20 de la Raspberry
bool senialmuneco=0, munecoflag=0;
unsigned long tiempo_inicio_muneco=0;
static int PinModo = 8;       // GPIO21 de la Raspberry. HIGH = modo felicidad
bool modo_felicidad=0, modo_anterior=0;

int tiempo_pare = 5000;       // ms que frena ante un PARE
int tiempo_ignorar_pare = 15000; // ms desde el PARE en que no vuelve a frenar, para poder pasar el cartel
unsigned long tiempo_muneco = 10000; // ms que frena ante el muñeco
unsigned long tiempo_ignorar_muneco = 15000; // ms despues de volver a arrancar en que no vuelve a frenar por el muñeco

// --- Modo felicidad: arranca despacio y, yendo recto, acelera de a poco
int vel_min_remoto = 110;     // al arrancar, al girar y al cambiar de sentido
int vel_max_remoto = 150;     // tope yendo recto
int paso_remoto = 5;          // cuanto sube cada vez...
int cada_remoto = 150;        // ...y cada cuantos ms (110 -> 150 en ~1.2 s)
int vel_remoto = vel_min_remoto;
bool reversa_anterior = 0;
unsigned long ultimo_aumento = 0;


int digital[4];
int sensoresanalog[4];
long int sumap, suma, pos, poslast, posicion;

// --- UMBRAL DE SENSIBILIDAD ---
int UMBRAL = 400;

float KP=0.5;
float KD=0.3;
float KI=0.01;

/// datos para la integral
int error1=0;
int error2=0;
int error3=0;
int error4=0;
int error5=0;
int error6=0;
/////////////////////////

///////////variable PID///////////////
int proporcional=0;
int integral=0;
int derivativo=0;
int diferencial=0;
int last_prop;
int setpoint=200;


void setup() {
  Serial.begin(9600);
  pinMode(PinIN1, OUTPUT);
  pinMode(PinIN2, OUTPUT);
  pinMode(PinIN3, OUTPUT);
  pinMode(PinIN4, OUTPUT);
  // Sin PULLUP: con pullup, si el programa de la Raspberry se corta los pines
  // quedan sueltos y se leen en HIGH, y eso en modo felicidad es "los dos
  // motores a fondo". Sin pullup manda el pull-down de la Raspberry: todo en LOW.
  pinMode(PinSemaforo, INPUT);
  pinMode(PinPare, INPUT);
  pinMode(PinMuneco, INPUT);
  pinMode(PinModo, INPUT);

  Serial.println("--- Inicio de Depuración ---");
}



void loop() {

  modo_felicidad = digitalRead(PinModo);
  if (modo_felicidad != modo_anterior){
    // Al cambiar de modo se frena y se arranca de cero: al volver al modo
    // normal espera otra vez el semaforo verde.
    motores(0,0);
    arranque=0;
    stopflag=0;
    munecoflag=0;
    vel_remoto = vel_min_remoto;
    modo_anterior = modo_felicidad;
  }

  if (modo_felicidad==1){
    manejo_remoto();
    return;
  }

  if (arranque==0){
    semaforo_verde = digitalRead(PinSemaforo);  // HIGH si la Raspberry manda señal
    if (semaforo_verde==1)
      arranque=1;
  }

  if(arranque==1){
    posicion=lectura();
    PID();
    frenos();
  }

  senialpare = digitalRead(PinPare);  // HIGH si la Raspberry manda señal
  tiempo_actual = millis();

  if(senialpare==1 && stopflag==0){
    motores(0,0);
    delay(tiempo_pare);
    tiempo_inicio=tiempo_actual;
    stopflag=1;
  }

  if(stopflag==1){
    tiempo_pasado = tiempo_actual - tiempo_inicio;
      if(tiempo_pasado >= tiempo_ignorar_pare){
        stopflag=0;
      }
  }

  // Como el PARE, pero el tiempo de ignorar se cuenta desde que vuelve a
  // arrancar, no desde que lo vio: si no, con 10 s frenado casi no lo pasaria.
  senialmuneco = digitalRead(PinMuneco);
  if(senialmuneco==1 && munecoflag==0){
    motores(0,0);
    delay(tiempo_muneco);
    tiempo_inicio_muneco=millis();
    munecoflag=1;
  }

  if(munecoflag==1 && millis() - tiempo_inicio_muneco >= tiempo_ignorar_muneco){
    munecoflag=0;
  }

  Serial.print(posicion);
  /*
  Serial.print("         proporcional:  ");
  Serial.print(proporcional);
  */
  Serial.println();

  Serial.print("                                 Valores[ei,mi,md,ed]:    ");
  for (int i=0; i<4; i++){
    Serial.print(sensoresanalog[i]);
    Serial.print("\t");
  }
  Serial.print("          ");

  //Serial.print("       semaforo verde, arranque, senialpare, stopflag   "); Serial.print(semaforo_verde); Serial.print(arranque); Serial.print(senialpare); Serial.print(stopflag);
  
}

// Modo felicidad: cada pin prende un motor y el del muñeco los pone en reversa.
// W = los dos, S = los dos en reversa, A = solo el derecho, D = solo el izquierdo.
void manejo_remoto(){
  bool motor_izq = digitalRead(PinPare);
  bool motor_der = digitalRead(PinSemaforo);
  bool reversa = digitalRead(PinMuneco);

  // Recto (los dos motores, mismo sentido) acelera de a poco hasta el tope.
  // Girando, quieto o al cambiar de sentido vuelve a la minima.
  if(motor_izq && motor_der && reversa == reversa_anterior){
    if(millis() - ultimo_aumento >= cada_remoto && vel_remoto < vel_max_remoto){
      vel_remoto += paso_remoto;
      if(vel_remoto > vel_max_remoto) vel_remoto = vel_max_remoto;
      ultimo_aumento = millis();
    }
  }
  else{
    vel_remoto = vel_min_remoto;
    ultimo_aumento = millis();
  }
  reversa_anterior = reversa;

  int vel = reversa ? -vel_remoto : vel_remoto;
  motores(motor_izq ? vel : 0, motor_der ? vel : 0);
}

void motores(int izq, int der){//0 hasta 255    0 hasta -255
  izq=constrain(izq,-255,255);
  der=constrain(der,-255,255);
  ////////////////motor LEFT "IZQUIERDO" ////////////////////////
  if(izq>=0){
    digitalWrite(PinIN2,HIGH);
    digitalWrite(PinIN1,LOW);
    analogWrite(PinIN2,izq);
  }
  else{
    digitalWrite(PinIN2,LOW);
    digitalWrite(PinIN1,HIGH);
    izq=izq*(-1);
    analogWrite(PinIN1,izq);
  }

  ////////////////motor RIGHT "DERECHO" ////////////////////////
  if(der>=0){
    digitalWrite(PinIN3,HIGH);
    digitalWrite(PinIN4,LOW);
    analogWrite(PinIN3,der);
  }
  else{
    digitalWrite(PinIN3,LOW);
    digitalWrite(PinIN4,HIGH);
    der=der*(-1);
    analogWrite(PinIN4,der);
  }
  /*
  Serial.print("motores:    ");
  Serial.print(izq); Serial.print("  "); Serial.print(der);
  Serial.println(" ");
  */
}


// Variables globales nuevas
int vel_min = 120;   // velocidad mínima    en 120 andaba bien, aunque un poco lento 
int vel_max = 180;   // velocidad máxima    en 220 andaba bien
int vel_base = vel_min;  // velocidad actual
int recto_counter = 0; // cuenta cuántos ciclos va recto

void PID(){
  proporcional = pos - setpoint;
  derivativo = proporcional - last_prop;
  integral = error1 + error2 + error3 + error4 + error5 + error6;
  last_prop = proporcional;

  // actualizar historial de errores para la integral
  error6 = error5;
  error5 = error4;
  error4 = error3;
  error3 = error2;
  error2 = error1;
  error1 = proporcional;

  int diferencial = (proporcional*KP) + (derivativo*KD) + (integral*KI);

  // --- Control de velocidad según si va recto o en curva ---
  if (abs(proporcional) < 70) {  // con 4 sensores, uno solo de los del medio da 67: sigue contando como recto
    // casi centrado en la línea
    recto_counter++;
    if (recto_counter > 3 && vel_base < vel_max) { 
      vel_base += 20; // subir velocidad progresivamente en +=15 estaba bien
    }
  } else if (abs(proporcional) > 160)  {  // agregue este if para que no desacelere en la parte recta. probar con otro if de abs proporcional entre 60 y 160 que baje -=5
    recto_counter = 0;
    //vel_base -= 30;  // frenar rápido al entrar en curva   en -=5 estaba bien     bajarlo un poco para que no desacelere en la parte recta
    vel_base = vel_min;
    if (vel_base < vel_min) vel_base = vel_min;
  }
  else  if (abs(proporcional) >= 60 && abs(proporcional) <= 160){  // agregue este if para que no desacelere tanto en la parte recta. prueba con if de abs proporcional entre 60 y 160 que baje -=5
    recto_counter = 0;
    vel_base -= 5; 
    if (vel_base < vel_min) vel_base = vel_min;
  }


  // --- Aplicar corrección con la velocidad adaptada ---
  if(diferencial < 0)
    motores(vel_base, vel_base + diferencial);
  else
    motores(vel_base - diferencial, vel_base);
}


int lectura(void){
  sensoresanalog[0] = analogRead(Pin_sensor_eizq);
  sensoresanalog[1] = analogRead(Pin_sensor_mizq);
  sensoresanalog[2] = analogRead(Pin_sensor_mder);
  sensoresanalog[3] = analogRead(Pin_sensor_eder);

  // Los del medio con umbral bajo y los extremos con UMBRAL, como antes.
  digital[0] = sensoresanalog[0] > UMBRAL;
  digital[1] = sensoresanalog[1] > 120;
  digital[2] = sensoresanalog[2] > 120;
  digital[3] = sensoresanalog[3] > UMBRAL;

  // Misma escala que con 5 sensores (0 a 400, centro en 200) para no tener
  // que recalibrar el PID: los 4 sensores quedan repartidos en ese rango.
  // Linea entre los dos del medio = 200.
  sumap=400*digital[0]+267*digital[1]+133*digital[2]+0*digital[3];
  suma=digital[0]+digital[1]+digital[2]+digital[3];
  if(suma>0)
    pos=(sumap/suma);
  else
    pos=poslast;  // antes dividia por cero; los casos de linea perdida van abajo

  // Sensores prendidos con uno apagado en el medio (ej. 1,0,1,0): se esta
  // pisando una de las lineas externas al circuito, ignorar la medicion.
  int primero=-1, ultimo=-1;
  for (int i=0; i<4; i++){
    if (digital[i]==1){
      if (primero<0) primero=i;
      ultimo=i;
    }
  }
  if (suma>0 && (ultimo-primero+1) != suma)
    {pos=poslast;
    Serial.print("     linea externa pisada   ");
    }
  if(poslast<=60 && suma==0){
    pos=0;
  }
  if(poslast>=340 && suma==0){
    pos=400;
  }
  poslast=pos;
  return pos; 
}

int veladelante=170, velatras=80;
void frenos(){
  if(pos<=40){  // lo cambie, antes estaba este en 60 y el otro en 340
    motores(veladelante, -velatras);
    Serial.print("     FRENO DER   ");
  }
  if(pos>=360){
    motores(-velatras, veladelante);
    Serial.print("     FRENO IZQ   ");
  }
}
