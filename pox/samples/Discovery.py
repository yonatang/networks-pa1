import utils
from DataModel import DataModel
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.ethernet      import ethernet
from pox.lib.packet.lldp          import lldp, chassis_id, port_id, end_tlv
from pox.lib.packet.lldp          import ttl, system_description
from pox.core import core
from threading import Lock
log = core.getLogger()

class Discovery:
    '''
    This class learn the network topology, and saves it in the DataModel class
    its sends periodic (every DISCOVERY_INTERVAL ) LLDP packets to all connected switches, and updated the topology accordingly
    in addition its also remove links from the graph when they didn't been active for the X seconds or an indication for link loss occours  
    '''
    __metaclass__ = utils.SingletonType
  
    LLDP_DST_ADDR  = '\x01\x80\xc2\x00\x00\x0e'
    DISCOVERY_INTERVAL = 1
    REMOVE_EXPIRED_INTERVAL = 3

    def __init__(self):
        '''
        Constructor
        '''        
        self.connected_switches = []
        self.discovery_timer = utils.Timer(Discovery.DISCOVERY_INTERVAL, self._send_discovery_packets, [], True)
        self.remove_expired_timer = utils.Timer(Discovery.REMOVE_EXPIRED_INTERVAL, self._remove_expired_links, [], True)
        self.graph = DataModel()
        self.handlers = []
        self.change_lock = Lock()
    
    def _remove_expired_links(self):
        expired_links=self.graph.get_expired_links()
        if len(expired_links) > 0:
            log.debug('Discovery: removing %i expired links %s' %(len(expired_links),expired_links)) 
            for (a,port1,b,port2) in expired_links:
                self.graph.link_is_dead(a, port1, b, port2)
            print "Expired - allowed links %s" % (self.graph.get_all_allowed_links())
            print "Expired - forbidden links %s" % (self.graph.get_all_forbidden_links())
            self._tree_changed()
            #self.graph.delete_expired_links()
            
    
    def _send_discovery_packets(self):
        '''
            sends discovery packets to all connected switches
        '''
        #log.debug('Discovery: sending LLDP to %i connected switches' % (len(self.connected_switches)) )        
        for switch_event in self.connected_switches:
            self.send_LLDP_to_switch(switch_event)

    def send_LLDP_to_switch(self,event):
        '''
        sending lldp packet to all of a switch ports        
        :param event: the switch ConnectionUp Event
        '''
        dst = Discovery.LLDP_DST_ADDR
        for p in event.ofp.ports:
            if p.port_no < of.OFPP_MAX:  # @UndefinedVariable
                # Build LLDP packet
                src = str(p.hw_addr)
                port = p.port_no

                lldp_p = lldp() # create LLDP payload
                ch_id=chassis_id() # Add switch ID part
                ch_id.fill(ch_id.SUB_LOCAL,bytes(hex(long(event.dpid))[2:-1])) # This works, the appendix example doesn't
                #ch_id.subtype=chassis_id.SUB_LOCAL
                #ch_id.id=event.dpid
                lldp_p.add_tlv(ch_id)
                po_id = port_id() # Add port ID part
                po_id.subtype = 2
                po_id.id = str(port)
                lldp_p.add_tlv(po_id)
                tt = ttl() # Add TTL
                tt.ttl = 1
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
        self.set_LLDP_rule(event.connection)
        log.debug('Discovery: switch %i connected'%(event.dpid))
        self.graph.switch_is_up(event.dpid)
        
    def set_LLDP_rule(self,connection):
        '''
        set a flow rule in the switch
        to pass all LLDP packets to the controller
        '''
        # should i delete old rules ?
                
        fm = of.ofp_flow_mod()
        fm.match.dl_type = ethernet.LLDP_TYPE
        fm.match.dl_dst = Discovery.LLDP_DST_ADDR

        # Add an action to send to the specified port
        action = of.ofp_action_output(port=of.OFPP_CONTROLLER)  # @UndefinedVariable
        fm.actions.append(action)
        # Send message to switch
        connection.send(fm)
        
    def _handle_ConnectionDown(self, event):
        '''
        Will be called when a switch goes down. Use event.dpid for switch ID.
        '''
        event_to_delete = [up_event for up_event in self.connected_switches if up_event.dpid == event.dpid][0]
        self.connected_switches.remove(event_to_delete)
        log.debug('Discovery: switch %i disconnected'%(event.dpid))
        
        self.graph.switch_is_down(event.dpid)
        #self._tree_changed()
        
    def _handle_PortStatus(self, event):
        '''
        Will be called when a link changes. Specifically, when event.ofp.desc.config is 1, it means that the link is down. Use event.dpid for switch ID and event.port for port number.
        '''
        dpid=event.dpid
        port=event.port
        if event.ofp.desc.config == 1:
            #self.graph.link_is_dead(event.dpid, event.port)
            log.debug('[switch %i]: port %i was disconnected'%(dpid, port))
            links = self.graph.get_all_links_for_switch_and_port(dpid, port)
            log.debug('[switch %i]: mark the following links as dead: %s' % (dpid,links))
            for (s1,p1,s2,p2) in links:
                self.graph.link_is_dead(s1, p1, s2, p2)
            if (len(links)>0):
                self._tree_changed()
            
                
    def _handle_PacketIn(self, event):
        '''
        Will be called when a packet is sent to the controller. Same as in the previous part. Use it to find LLDP packets (event.parsed.type == ethernet.LLDP_TYPE) and update the topology according to them.
        '''
        if event.parsed.type != ethernet.LLDP_TYPE:
            return
        
        pkt = event.parsed
        lldp_p = pkt.payload
        ch_id = lldp_p.tlvs[0]
        po_id = lldp_p.tlvs[1]
        src_dpid = int(ch_id.id)
        src_port = int(po_id.id)
        #log.debug("Received a LLDP packet on switch %i from %i" % (event.dpid,src_dpid))
        self.graph.link_is_alive( src_dpid, src_port, event.dpid, event.port)
        self._tree_changed()
            
        
    def register_tree_change(self,handler):
        self.handlers.append(handler)

    def _tree_changed(self):
        self.change_lock.acquire()
        try:
            allowed=self.graph.get_all_allowed_links()
            forbidden=self.graph.get_all_forbidden_links()
            to_add=self.graph.get_enteries_to_add()
            to_remove=self.graph.get_enteries_to_remove()
            for handler in self.handlers:
                handler.handle(allowed,forbidden)
            
            for (s1,p1,s2,p2) in to_add:
                self.graph.enteries_added(s1, p1, s2, p2)
                
            for (s1,p1,s2,p2) in to_remove:
                self.graph.enteries_removed(s1, p1, s2, p2)
        finally:    
            self.change_lock.release()

        