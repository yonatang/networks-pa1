""" OpenFlow Exercise - Sample File
This file was created as part of the course Advanced Workshop in IP Networks
in IDC Herzliya.

This code is based on the official OpenFlow tutorial code.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.samples.Discovery import Discovery
from pox.lib.packet.ethernet import ethernet
log = core.getLogger()

class Switch2 (object):
    """
    A Switch object is created for each switch that connects.
    A Connection object for that switch is passed to the __init__ function.
    """
    def __init__ (self, connection):
        self.connection = connection
        self.ports = {}
        #self.map_ports_to_eths = {}
        self.discovery=Discovery()
        self.forbidden_ports=[]
        
        # This binds our PacketIn event listener
        connection.addListeners(self)
        # This binds the discovery PacketIn event listener
        connection.addListeners(self.discovery)
        # This binds the switch to topology changes
        self.discovery.register_tree_change(self)
        

    def _handle_PacketIn (self, event):
        """
        Handles packet in messages from the switch.
        """
  
        packet = event.parsed # Packet is the original L2 packet sent by the switch
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return
    
        packet_in = event.ofp # packet_in is the OpenFlow packet sent by the switch
    
        self.act_like_switch(packet, packet_in)
    
    def remove_flow_rule(self, dst_eth, port):
        flow_msg=of.ofp_flow_mod()
        flow_msg.match.dl_dst=dst_eth
        flow_msg.command=of.OFPFC_DELETE
        self.connection.send(flow_msg)
        self.discovery.set_LLDP_rule(self.connection)
        log.debug('[switch %i] flow record removed: match[dl_dst=%s] -> out_port=%i' % (self.connection.dpid, dst_eth, port))
        
    def __flood(self, packet_in):
        ports=self.connection.features.ports
        
        buffer_id = packet_in.buffer_id
        raw_data = packet_in.data
        in_port=packet_in.in_port
        msg=of.ofp_packet_out()
        if buffer_id != -1 and buffer_id is not None:
            # We got a buffer ID from the switch; use that
            msg.buffer_id = buffer_id
        else:
            # No buffer ID from switch -- we got the raw data
            if raw_data is None:
                # No raw_data specified -- nothing to send!
                return
            msg.data = raw_data
            
        for port in ports:
            port_no=port.port_no
            if (port_no < of.OFPP_MAX) and (port_no != in_port) and (port_no not in self.forbidden_ports):
                #print '[switch %i] (flooding) adding action from in_port=%i to out_port=%i' % (self.connection.dpid, in_port,port_no)
                action = of.ofp_action_output(port = port_no)
                msg.actions.append(action)
        
        self.connection.send(msg)
    
    def handle(self, allowed_links, forbidden_links):
        """
        Implement the topology-change handler 
        """
        #forbidden_links=datamodel.get_all_forbidden_links()
        #entries_to_remove=datamodel.get_enteries_to_remove()
        dpid=self.connection.dpid
        #self.forbidden_ports=[]
        new_forbidden_ports=[]
        new_allowed_ports=[]
        for (s1,p1,s2,p2) in forbidden_links:
            if (s1==dpid):
                new_forbidden_ports.append(p1)
            if (s2==dpid):
                new_forbidden_ports.append(p2)
        
        for (s1,p1,s2,p2) in allowed_links:
            if (s1==dpid):
                new_allowed_ports.append(p1)
            if (s2==dpid):
                new_allowed_ports.append(p2)
        
        
                
        for port in new_forbidden_ports:
            if port not in self.forbidden_ports:
                log.debug("[switch %i] spanning tree disabled port %i" % (dpid,port))
                
                for (eth,e_port) in self.ports.items():
                    if e_port==port:
                        self.remove_flow_rule(eth, port)

        for port in new_allowed_ports:
            if port in self.forbidden_ports:
                log.debug("[switch %i] spanning tree enabled port %i" % (dpid,port))
                        
        self.forbidden_ports=new_forbidden_ports
                
        
    def act_like_switch(self, packet, packet_in):
        """
        Implement switch-like behaviour
        """
        eth_src = packet.src
        eth_dst = packet.dst
        buffer_id = packet_in.buffer_id
        raw_data = packet_in.data
        in_port = packet_in.in_port
        
        if packet.type == ethernet.LLDP_TYPE:
            return
        
        if in_port in self.forbidden_ports:
            return
        
        if (eth_src in self.ports) and (self.ports[eth_src] != packet_in.in_port):
            self.remove_flow_rule(eth_src, self.ports[eth_src])
        
        # learn locally about the port for this Ethernet address port
        # don't add a rule yet, because we need to filter packets by the in_port as well
        self.ports[eth_src] = packet_in.in_port
        
        if eth_dst in self.ports:
            # we know everything in order to set the flowtable rule now
            out_port = self.ports[eth_dst]
            msg = of.ofp_flow_mod()
            msg.match.dl_dst = eth_dst
            msg.match.in_port = in_port
            msg.match.dl_src = eth_src
            log.debug('[switch %i] flow record added: match[in_port=%i,dl_src=%s,dl_dst=%s] -> out_port=%i' % (self.connection.dpid, in_port, eth_src, eth_dst, out_port))
            msg.in_port = in_port
            if buffer_id != -1 and buffer_id is not None:
                # We got a buffer ID from the switch; use that
                msg.buffer_id = buffer_id
            else:
                # No buffer ID from switch -- we got the raw data
                if raw_data is None:
                    # No raw_data specified -- nothing to send!
                    return
                msg.data = raw_data
        
            # Add an action to send to the specified port
            action = of.ofp_action_output(port = out_port)
            msg.actions.append(action)
        
            # Send message to switch
            self.connection.send(msg)
        else:
            log.debug('[switch %i] flooding packet [dl_src=%s,dl_dst=%s,in_port=%i]' % (self.connection.dpid, eth_src, eth_dst, in_port))
            self.__flood(packet_in)
                  
            
        

def launch ():
    """
    Starts the component
    """
    def start_switch (event):
        log.debug("Controlling %s" % (event.connection,))
        Switch2(event.connection)
    core.openflow.addListenerByName("ConnectionUp", start_switch)
