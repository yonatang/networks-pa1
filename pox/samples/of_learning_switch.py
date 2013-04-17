""" OpenFlow Exercise - Sample File
This file was created as part of the course Advanced Workshop in IP Networks
in IDC Herzliya.

This code is based on the official OpenFlow tutorial code.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

class Switch (object):
    """
    A Switch object is created for each switch that connects.
    A Connection object for that switch is passed to the __init__ function.
    """
    def __init__ (self, connection):
        self.connection = connection
        self.ports = {}

        # This binds our PacketIn event listener
        connection.addListeners(self)

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
    
    def remove_flow_rule(self, dst_eth):
        flow_msg=of.ofp_flow_mod()
        flow_msg.match.dl_dst=dst_eth
        flow_msg.command=of.OFPFC_DELETE
        self.connection.send(flow_msg)
        
    def act_like_switch(self, packet, packet_in):
        """
        Implement switch-like behavior
        """
        eth_src = packet.src
        eth_dst = packet.dst
        buffer_id = packet_in.buffer_id
        raw_data = packet_in.data
        in_port = packet_in.in_port
        
        if (eth_src in self.ports) and (self.ports[eth_src] != packet_in.in_port):
            log.debug('[switch %i] flow record removed: match[dl_dst=%s] -> out_port=%i' % (self.connection.dpid, eth_src, self.ports[eth_src]))
            self.remove_flow_rule(eth_src)
        
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
        else:
            out_port = of.OFPP_FLOOD
            msg = of.ofp_packet_out()
            log.debug('[switch %i] flooding packet [dl_src=%s,dl_dst=%s,in_port=%i]' % (self.connection.dpid, eth_src, eth_dst, in_port))      
            
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

def launch ():
    """
    Starts the component
    """
    def start_switch (event):
        log.debug("Controlling %s" % (event.connection,))
        Switch(event.connection)
    core.openflow.addListenerByName("ConnectionUp", start_switch)
