try:
    from _winreg import *
except Exception, e:
    print "WARNING: Could not import _winreg. Live system registry analysis cannot be done. You MUST specify a registry hive file."
import argparse
from regparser import RegParser
from datetime import *
import traceback

class USBInfo:
    def __init__(self):
        self.properties = None
    
    def addProperty(self, key, value):
        if self.properties is None:
            self.properties = []
        self.properties += [(key,value)]
    
    def __str__(self):
        if self.properties == None:
            return None
        out = ""
        for p in self.properties:
            out += "%-20s: %s\r\n" % p
        return out
        
    def __repr__(self):
        return self.__str__() + "\r\n"
            
class DeviceClass:
    def __init__(self, hardwareID = None, instanceID = None):
        self.hardwareID = hardwareID
        self.instanceID = instanceID
    
    def __str__(self):
        return "(HW_ID: %s, I_ID: %s)" % (self.hardwareID, self.instanceID)
    
    def __repr__(self):
        return self.__str__()
        
def parseHardwareInstance(deviceInstance = None):
    if deviceInstance is None:
        return None
    
    if deviceInstance[0:4].upper() != "USB\\" and deviceInstance[0:8] != "USBSTOR\\":
        return None
    
    locSecondSlash = deviceInstance[4:].find("\\")
    if locSecondSlash is None:
        return None
        
    hardwareID = deviceInstance[4:4 + locSecondSlash]
    instanceID = deviceInstance[4 + locSecondSlash + 1:]
    
    return DeviceClass(hardwareID, instanceID)

'''Collect USB History from an NT registry file. File must be the "system" hive'''
def getUSBHistory_Offline(fileName, controlSet="CurrentControlSet"):
    rp = RegParser
    r = rp(fileName, "lolwut")
    
    controlSetKey = controlSet 
    deviceClassesKey = controlSetKey + "\\Control\\DeviceClasses"
    usbEnumKey = controlSetKey + "\\Enum\\USB"
    
    rk = r.getHiveRootKey()
    try:
        k = rp.openKey(rk, deviceClassesKey)
    except Exception, e:
        print e
        return None
    
    if k is None:
        return None
    usbHistories = []
    
    for i in range(1024):
        try:
            cdck = rp.openSubkeyByIndex(k, i)
            if cdck is None:
                break
            for h in range(1024):
                usbHistory = None
                try:
                
                    cdcs = rp.openSubkeyByIndex(cdck, h)
                    if cdcs is None:
                        break
                    devInstance = rp.getKeyValue(rp.openKey(cdck,cdcs.getKeyName()), "DeviceInstance")
            
                    di = parseHardwareInstance(devInstance)
                    if di is None:
                        continue
                    devKeyString = usbEnumKey + "\\" + di.hardwareID + "\\" + di.instanceID
                    hDevKey = rp.openKey(rk, devKeyString)
                    if hDevKey is None:
                        break
                    usbHistory = USBInfo()
                    firstCreated = rp.timestampToDatetime(rp.getKeyTimestamp(cdcs))
                    lastModified = rp.timestampToDatetime(rp.getKeyTimestamp(hDevKey))
                    usbHistory.addProperty("First Created", firstCreated)
                    usbHistory.addProperty("Last Modified", lastModified)
                    for j in range(1024):
                        try:
                            ui = rp.getKeyValueByIndex(hDevKey, j)
                            if ui is None:
                                continue
                        except Exception, e:
                            print traceback.format_exc()
                            print e
                            break
                        usbHistory.addProperty(ui[0],ui[1])
                    usbHistories += [usbHistory]
                except Exception, e:
                    print e
                    continue
        except Exception, e:
            print traceback.format_exc()
            print e
           # break
    return usbHistories
            
        
def getUSBHistory_Live(controlSet="CurrentControlSet"):
    usbHistories = []
    try:
        controlSetKey = "SYSTEM\\" + controlSet + "\\"
        deviceClassesKey = controlSetKey + "Control\\DeviceClasses\\"
        usbEnumKey = controlSetKey + "Enum\\USB\\"
        #deviceParamsKey = usbEnumKey + hardwareID + "\\" + instanceID + "\\" + "Device Parameters\\"
    
        hHive = ConnectRegistry(None, HKEY_LOCAL_MACHINE)
        startDate = datetime(1601, 1, 1)
    
        try:
            hDeviceClassesKey = OpenKey(hHive,  deviceClassesKey)
        except Exception, e:
            print e
            return None
    
        for i in range(1024):
        
            try:
                hCurrentDeviceClassKey = OpenKey(hDeviceClassesKey, EnumKey(hDeviceClassesKey, i))
                for h in range(1024):
                    usbHistory = None
                    try:
                        currentDeviceClassSubkey = EnumKey(hCurrentDeviceClassKey, h)
                        tmp = OpenKey(hCurrentDeviceClassKey, currentDeviceClassSubkey)
                        devInstance = QueryValueEx(OpenKey(hCurrentDeviceClassKey, currentDeviceClassSubkey), "DeviceInstance")[0]
                    
                        di = parseHardwareInstance(devInstance)
                        if di is None:
                            continue
                        #print "di -- %s" % str(di)
                        hDevKey = OpenKey(hHive, usbEnumKey + di.hardwareID + "\\" + di.instanceID + "\\")
                        usbHistory = USBInfo()

                        firstCreated = QueryInfoKey(tmp)[2]
                        lastModified = QueryInfoKey(hDevKey)[2]
                        usbHistory.addProperty("First Created", str(startDate + timedelta(seconds=firstCreated*(10**-9)*100)) + " UTC")
                        usbHistory.addProperty("Last Modified", str(startDate + timedelta(seconds=lastModified*(10**-9)*100)) + " UTC") 

                        for j in range(1024):
                            try:
                                ui = EnumValue(hDevKey, j)
                    
                            except Exception, e:
                                #print e
                                #print traceback.format_exc()
                                continue
                            
                            #print "ui -- %s" % str(ui)
                            usbHistory.addProperty(ui[0], ui[1])
                    except Exception, e:
                        #print traceback.format_exc()
                        continue
                    if usbHistory is not None:
                        usbHistories += [usbHistory]

            except Exception, e:
                print e
                print traceback.format_exc()
                break
    except Exception, e:
        print traceback.format_exc()
    return usbHistories

def main(winregLoaded):
    p = argparse.ArgumentParser(description="Search an offline or live system registry's USB History. Only works on NT registries")
    argGroup = p.add_mutually_exclusive_group(required=False)
    argGroup.add_argument("-f", "--hiveFileName", help="Full path+filename of the registry hive to parse")
    argGroup.add_argument("-l", "--live", help="Search a live system registry", const=1, nargs='?')
    args = p.parse_args()
    
    if winregLoaded and args.live is None:
        args.live = True
    controlSets = ["CurrentControlSet", "ControlSet001", "ControlSet002", "ControlSet003"]
    for c in controlSets:
        print c
        try:
            if winregLoaded is True:
                if args.live is not None:
                    print "Trying live..."
                    entries = getUSBHistory_Live(c)
                    
            else:
                entries = getUSBHistory_Offline(args.hiveFileName, c)
                
            if entries is not None:
                for e in entries:
                    print e
            
            else:
                Found no USB information
        except Exception, e:
            print e
            print "Exception"
    
    raw_input()
if __name__ ==  "__main__":
    winregAvailable = True
    try:
        import _winreg
    except Exception, e:
        print e
        winregAvailable = False
    main(winregAvailable)
