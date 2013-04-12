import utils
from datetime import datetime
import time


class LinkData:
    def __init__(self, port1, port2):
        self.last_sync = datetime.now()
        self.port1 = port1
        self.port2 = port2
        self.is_link_allowed = True
        self.has_entry = False

class SwitchData:
    def __init__(self):
        self.uf_rank = 0
        self.uf_parent = None

class DataModel:
    def __init__(self):
        self.graph = utils.Graph()

    """Should be called whenever an indication received, that a new switch is up"""
    def switch_is_up(self, switch_id):
        self.graph.add_node(switch_id, SwitchData())
        
    """Should be called whenever an indication received, that a switch is down.
    Returns the list of links that were removed"""
    def switch_is_down(self, switch_id):
        removed_links = []
        if switch_id in self.graph.nodes:
            self.graph.remove_node(switch_id)
            to_delete = []
            for (a,b) in self.graph.edges:
                if a == switch_id or b == switch_id:
                    to_delete.append((a,b))
            for (a,b) in to_delete:
                data = self.graph.edges[(a,b)]
                removed_links.append(a,data.port1,b,data.port2)
                self.graph.delete_edge(a, b)
            self.update_spanning_tree()
        return removed_links

    """Should be called whenever an indication received, that a link is down.
    Returns True if this link wasn't already dead"""
    def link_is_dead(self, s1_id, port1, s2_id, port2):
        link = self.graph.get_edge(s1_id, s2_id)
        if link != None and self.__check_ports(link, port1, port2):
            self.graph.delete_edge(s1_id, s2_id)
            self.update_spanning_tree()
            return True
        else:
            return False
              
    """Should be called whenever an indication received, that a link between two switches is alive.
    Returns True if this is a new link"""
    def link_is_alive(self, s1_id, port1, s2_id, port2):
        link = self.graph.get_edge(s1_id, s2_id)
        if link == None:
            link = LinkData(port1, port2)
            self.graph.add_edge(s1_id, s2_id, link)
            self.update_spanning_tree()
            return True
        else:
            link.last_sync = datetime.now()
            return False
            
    def get_all_links_for_switch_and_port(self,s_id,port):
        res = []
        for (a,b) in self.graph.edges:
            data = self.graph.edges[(a,b)]
            if (a==s_id) and (data.port1==port):
                res.append((a,data.port1,b,data.port2))
            if (b==s_id) and (data.port2==port):
                res.append((a,data.port1,b,data.port2))
        return res

    """Returns all the links which haven't shown life signs for more than 6 seconds.
       This method should be called from a different thread every 3 seconds.
       Each returned link should result with two entries removal.
       Also, link_is_dead() should be called for each returned link."""
    def get_expired_links(self):
        res = []
        now = datetime.now()
        for (a,b) in self.graph.edges:
            data = self.graph.edges[(a,b)]
            diff = now - data.last_sync
            if diff.seconds > 6:
                res.append((a,data.port1,b,data.port2))
        return res

    def __check_ports(self, link, port1, port2):
        return (link.port1 == port1 and link.port2 == port2) or (link.port1 == port2 and link.port2 == port1)

    """Should be called after a switches table entry is removed by the controller.
       Both entries on both sides of the link should be removed before calling this method"""
    def enteries_removed(self, s1_id, port1, s2_id, port2):
        link = self.graph.get_edge(s1_id, s2_id)
        if self.__check_ports(link, port1, port2):
            link.has_entry = False

    """Should be called after a switches table entry is added by the controller.
       Both entries on both sides of the link should be added before calling this method"""
    def enteries_added(self, s1_id, port1, s2_id, port2):
        link = self.graph.get_edge(s1_id, s2_id)
        if self.__check_ports(link, port1, port2):
            link.has_entry = True

    """Indicates whether a link is a part of the spanning tree, and is allowed to be used."""
    def is_link_allowed(self, s1_id, port1, s2_id, port2):
        link = self.graph.get_edge(s1_id, s2_id)
        return (link.is_link_allowed and self.__check_ports(link, port1, port2))
 
    """Returns all allowed links. Might be unuseful."""
    def get_all_allowed_links(self):
        res = []
        for (a,b) in self.graph.edges:
            data = self.graph.edges[(a,b)]
            if self.is_link_allowed(a, data.port1, b, data.port2):
                res.append((a,data.port1,b,data.port2))
        return res

    """Returns all forbidden links. Might be unuseful."""
    def get_all_forbidden_links(self):
        res = []
        for (a,b) in self.graph.edges:
            data = self.graph.edges[(a,b)]
            if not self.is_link_allowed(a, data.port1, b, data.port2):
                res.append((a,data.port1,b,data.port2))
        return res

    """Returns all the links that are forbidden, and the relevant entries haven't been removed yet by the controller."""
    def get_enteries_to_remove(self):
        res = []
        for (a,b) in self.graph.edges:
            data = self.graph.edges[(a,b)]
            if not self.is_link_allowed(a, data.port1, b, data.port2) and data.has_entry:
                res.append((a,data.port1,b,data.port2))
        return res

    """Returns all the links that are allowed, and the relevant entries haven't been added yet by the controller."""
    def get_enteries_to_add(self):
        res = []
        for (a,b) in self.graph.edges:
            data = self.graph.edges[(a,b)]
            if self.is_link_allowed(a, data.port1, b, data.port2) and not data.has_entry:
                res.append((a,data.port1,b,data.port2))
        return res

    """Updates the spanning tree. There is no need to call it, as it is called automatically in specific methods."""
    def update_spanning_tree(self):
        for v in self.graph.nodes:
            data = self.graph.nodes[v]
            utils.UnionFind.make_set(data)
        for (a,b) in self.graph.edges:
            data = self.graph.edges[(a,b)]
            data.is_link_allowed = False;
        for (a,b) in self.graph.edges:
            data1 = self.graph.nodes[a]
            data2 = self.graph.nodes[b]
            data = self.graph.edges[(a,b)]
            if utils.UnionFind.find(data1) != utils.UnionFind.find(data2):
                data.is_link_allowed = True;
                utils.UnionFind.union(data1, data2)
                
    def filter_forbidden_links(self, list_of_links):
        res = []
        for (a,port1,b,port2) in list_of_links:
            if self.is_link_allowed(a, port1, b, port2):
                res.append((a,port1,b,port2))
        return res




if __name__ == '__main__':
    """
    This is an example that shows all the usage patterns of the model.
    """
    print "Hello, World!"
    x = DataModel()
    
    """Adding 4 switches."""
    x.switch_is_up("s1")
    x.switch_is_up("s2")
    x.switch_is_up("s3")
    x.switch_is_up("s4")

    """Indications received that 6 links are alive."""
    x.link_is_alive("s1", 1111, "s2", 1111)
    x.link_is_alive("s1", 2222, "s3", 2222)
    x.link_is_alive("s1", 3333, "s4", 3333)
    x.link_is_alive("s2", 4444, "s3", 4444)
    x.link_is_alive("s2", 5555, "s4", 5555)
    x.link_is_alive("s3", 6666, "s4", 6666)
    
    """Watch the result in debbug mode. y1 contains the spanning tree."""
    y1 = x.get_all_allowed_links()
    time.sleep(7)
    x.link_is_alive("s1", 1111, "s2", 1111)
    x.link_is_alive("s1", 3333, "s4", 3333)
    x.link_is_alive("s2", 4444, "s3", 4444)
    x.link_is_alive("s3", 6666, "s4", 6666)
    
    """Watch the result in debug mode."""
    expired = x.get_expired_links()
    
    for (a,port1,b,port2) in expired:
        x.link_is_dead(a, port1, b, port2)
    
    """Watch the results in debug mode. y4 contains the new spanning tree."""
    y3 = x.get_all_forbidden_links()
    y4 = x.get_all_allowed_links()
    
    """Watch the results in debug mode. No entries exist yet."""
    y5 = x.get_enteries_to_add()
    y6 = x.get_enteries_to_remove()
    
    """The controller has added the relevant entries for 2 links."""
    x.enteries_added("s3", 6666, "s4", 6666)
    x.enteries_added("s2", 4444, "s3", 4444)
    
    """Watch the results in debug mode. These should be different than y5 and y6."""
    y7 = x.get_enteries_to_add()
    y8 = x.get_enteries_to_remove()
    
    """An indication received that a switch is down"""
    x.switch_is_down("s4")
    
    """Watch the results in debug mode.
       The spanning tree is different now, as the graph has less nodes and edges."""
    y9 = x.get_all_allowed_links()
    