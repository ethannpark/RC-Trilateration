#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define BEACON_NUMBER       "1"

void setup() {
  Serial.begin(115200);

  char name[20];
  sprintf(name, "B%d", BEACON_NUMBER);
  if (!BLEDevice::init(name)) {
    Serial.println("BLE initialization failed!");
    return;
  }

  BLEDevice::setPower(ESP_PWR_LVL_P20, ESP_BLE_PWR_TYPE_ADV); //+20 Dbm
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService(SERVICE_UUID);
  BLECharacteristic *pCharacteristic =
    pService->createCharacteristic(CHARACTERISTIC_UUID, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE);

  char value[20];
  sprintf(value, "Beacon %d", BEACON_NUMBER);
  pCharacteristic->setValue(value);
  pService->start();


  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(false);
  pAdvertising->setMinPreferred(0x06); 
  pAdvertising->setMaxPreferred(0x12);
  BLEDevice::startAdvertising();
}

void loop() {
  delay(2000);
}
