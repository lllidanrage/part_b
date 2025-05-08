import math
from enum import Enum
from referee.game.player import PlayerColor



class Node:
    def __init__(self, state, parent=None):
        # Initialize the node with state, parent, children list, rewards, and visits
        self.state = state
        self.parent = parent
        self.children = []
        self.total_rewards = [0.0, 0.0]  # Assuming two players
        self.visits = 0
        self.untried_actions = state.get_legal_actions()
        if parent is not None:
            parent.children.append(self)
    
    def best_child(self):
        # Calculate the best child using the UCB algorithm
        exploration_weight = math.sqrt(2)  # Exploration weight
        current_player_color = self.state.board.turn_color  # Current player color

        def ucb(child:None)->float:
            # Calculate UCB value
            if child.visits == 0:
                return float('inf')  # Prioritize unexplored nodes
            # UCB formula: Exploit + Explore
            return (child.total_rewards[current_player_color] / child.visits + 
                   exploration_weight * math.sqrt(math.log(self.visits) / child.visits))
        
        return max(self.children, key=ucb)  # Return the child with the highest UCB value
    
    def expand(self):
        action = self.untried_actions.pop()
        next_state = self.state.get_next_state(action)
        child_node = Node(next_state, self)
        self.children.append(child_node)
        return child_node
    
    
    def __repr__(self):
        return f"Node({self.name})"

    def add_child(self, child_node):
        # Add a child node
        self.children.append(child_node)
        child_node.parent = self

    def remove_child(self, child_node):
        # Remove a child node
        self.children.remove(child_node)
        child_node.parent = None

    def get_children(self):
        # Get all child nodes
        return self.children