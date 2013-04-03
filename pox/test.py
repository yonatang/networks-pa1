import sys
from pox.lib.addresses import *

class Main():
    def __init__(self):
        self.ports={}
        
    def put(self,key,val):
        self.ports[key]=val
        
    def get(self,key):
        return self.ports[key]
    
    def check(self,key):
        return key in self.ports
        
def main():
    print "Hello, world"
    m=Main()
    m.put("abc","value")
    print m.get("abc")
    print m.check("abc")
    a=EthAddr(b"\x00\x00\x00\x00\x00\x00")
    b=EthAddr(b"\x00\x00\x00\x00\x00\x01")
    m.put(a,"aaa")
    print m.check(b)
    print a.toStr()
    print str(a)
    print a
    print ''.join([str(1)])

main()