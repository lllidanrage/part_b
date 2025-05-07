import math

from referee.game import Direction, Coord, MoveAction
from referee.game.player import PlayerColor


class Node:
    def __init__(self, state, parent=None):
        self.state = state
        self.parent = parent
        self.children = []
        self.total_rewards = [0.0, 0.0]  # red, blue
        self.visits = 0
        self.unexplored_actions = state.get_legal_actions()

    def select_child(self):
        """
        Select the child with the highest UCB1 value.
        """
        exploration_constant = math.sqrt(2)

        current_player = 0 if self.state.board.turn_color == PlayerColor.RED else 1

        def ucb(child) -> float:
            if child.visits == 0:
                return float('inf')

            return (child.total_rewards[current_player] / child.visits +
                    exploration_constant * math.sqrt(math.log(self.visits) / child.visits))

        return max(self.children, key=ucb)

    def expand(self):
        action = self.unexplored_actions.pop()
        next_state = self.state.move(action)
        child = Node(next_state, parent=self)
        self.children.append(child)
        return child

    def update(self, reward):
        self.visits += 1

        if self.state.board.turn_color == PlayerColor.RED:
            self.total_rewards[0] += reward
            self.total_rewards[1] -= reward
        else:
            self.total_rewards[1] += reward
            self.total_rewards[0] -= reward

class MCTS:
    def __init__(self,
                 state,
                 num_simulations: int = 1000,
                 exploration_constant: float = 1.4):
        self.state = state
        self.num_simulations = num_simulations
        self.exploration_constant = exploration_constant
        self.root = Node(state)


class GameState:
    def __init__(self, last_move, board):
        self.last_move = last_move
        self.board = board

    def get_legal_actions(self, coord):
        visited = set()

        default_directions = [
            Direction.Up,
            Direction.UpLeft,
            Direction.UpRight,
            Direction.Down,
            Direction.DownLeft,
            Direction.DownRight,
        ]

        red_directions = [
            Direction.Down,
            Direction.DownLeft,
            Direction.DownRight,
            Direction.Left,
            Direction.Right
        ]

        blue_directions = [
            Direction.Up,
            Direction.UpLeft,
            Direction.UpRight,
            Direction.Left,
            Direction.Right
        ]

        def evaluate_action(action):
            pass

        def normal_move(curr_coord, directions):
            for direction in directions:
                try:
                    next_coord = curr_coord + direction
                    if self.board[next_coord].state == "LilyPad":
                        action = MoveAction(curr_coord, (direction,))
                        evaluate_action(action)
                except ValueError:
                    continue

        def jump_move(curr_coord, path: list[Direction], directions):
            if self.board[curr_coord].state != self.board.turn_color:
                return

            if path:
                action = MoveAction(curr_coord, tuple(path.copy()))
                evaluate_action(action)

            for direction in directions:
                try:
                    route_coord = curr_coord + direction
                    next_coord = route_coord + direction
                    if (self.board[route_coord].state in (PlayerColor.RED, PlayerColor.BLUE) and
                            self.board[next_coord].state == 'LilyPad'):
                        new_direction = path + [direction]

                        if next_coord not in visited:
                            visited.add(next_coord)
                            jump_move(next_coord, new_direction, directions)
                            visited.remove(next_coord)
                except ValueError:
                    continue


if __name__ == '__main__':
    pass
