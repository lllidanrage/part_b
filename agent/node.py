import math
from enum import Enum

class Player(Enum):
    PLAYER_BLUE = 1
    PLAYER_RED = 0

class NNode:
    def __init__(self, state, parent=None):
        self.state = state
        self.parent = parent
        self.children = []
        self.total_rewards = [0.0, 0.0]  # Assuming two players
        self.visits = 0
        self.untried_actions = state.get_legal_actions()
        if parent is not None:
            parent.children.append(self)
    
    def best_child(self):
        exploration_weight = math.sqrt(2)
        current_player = Player.PLAYER_RED if self.state.board.turn_color else Player.PLAYER_BLUE

    def __repr__(self):
        return f"Node({self.name})"

    def add_child(self, child_node):
        self.children.append(child_node)
        child_node.parent = self

    def remove_child(self, child_node):
        self.children.remove(child_node)
        child_node.parent = None

    def get_children(self):
        return self.children