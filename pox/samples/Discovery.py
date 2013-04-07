'''
Created on 6 באפר 2013

@author: user
'''
import utils
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ethernet      import ethernet
from pox.lib.packet.lldp          import lldp, chassis_id, port_id, end_tlv
from pox.lib.packet.lldp          import ttl, system_description

class Discovery:
    '''
    classdocs
    '''
    __metaclass__ = utils.SingletonType
  
    

    def __init__(self):
        '''
        Constructor
        '''
        DISCOVERY_INTERVAL = 1
        self.connected_switches = []
        self.timer = utils.Timer(DISCOVERY_INTERVAL, self._send_discovery_packets__, [], True)
      
    
    def __send_discovery_packets__(self):
        '''
            sends discovery packets to all connected switches
        '''
        for switch_event in self.connected_switches:
            self.send_lldp_to_switch(switch_event)
    

    def send_lldp_to_switch(self,event):
        '''
        sending lldp packet to all of a switch ports        
        :param event: the switch ConnectionUp Event
        '''
        dst = Discovery.LLDP_DST_ADDR # == '\x01\x80\xc2\x00\x00\x0e'
        for p in event.ofp.ports:
            if p.port_no < of.OFPP_MAX:
                # Build LLDP packet
                src = str(p.hw_addr)
                port = p.port_no
                lldp_p = lldp() # create LLDP payload
                ch_id = chassis_id() # Add switch ID part
                ch_id.subtype = 1
                ch_id.id = str(event.dpid)
                lldp_p.add_tlv(ch_id)
                po_id = port_id() # Add port ID part
                po_id.subtype = 2
                po_id.id = str(port)
                lldp_p.add_tlv(po_id)
                tt = ttl() # Add TTL
                tt.ttl = Discovery.LLDP_INTERVAL # == 1
                lldp_p.add_tlv(tt)
                lldp_p.add_tlv(end_tlv())
                ether = ethernet() # Create an Ethernet packet
                ether.type = ethernet.LLDP_TYPE # Set its type to LLDP
                ether.src = src # Set src, dst
                ether.dst = dst
                ether.payload = lldp_p # Set payload to be the LLDP payload
                # send LLDP packet
                pkt = of.ofp_packet_out(action = of.ofp_action_output(port = port))
                pkt.data = ether
                event.connection.send(pkt)  
            
    def _handle_ConnectionUp(self, event):
        '''
        Will be called when a switch is added.
        save the connection event in self.connected_switches 
        Use event.dpid for switch ID, and event.connection.send(...) to send messages to the switch.
        '''
        self.connected_switches.append(event)
        
    def _handle_ConnectionDown(self, event):
        '''
        Will be called when a switch goes down. Use event.dpid for switch ID.
        '''
    def _handle_PortStatus(self, event):
        '''
        Will be called when a link changes. Specifically, when event.ofp.desc.config is 1, it means that the link is down. Use event.dpid for switch ID and event.port for port number.
        '''
    def _handle_PacketIn(self, event):
        '''
        Will be called when a packet is sent to the controller. Same as in the previous part. Use it to find LLDP packets (event.parsed.type == ethernet.LLDP_TYPE) and update the topology according to them.
        '''
        
    def register_tree_change(self,handler):
        self.handler = handler

    def _tree_changed(self):
        self.hanlder()

        