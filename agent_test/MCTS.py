import math
import random
from collections import defaultdict
from copy import deepcopy

from referee.game import Direction, MoveAction, GrowAction, IllegalActionException, BOARD_N, Board
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
    def __init__(self, state):
        self.root = Node(state)

    def search(self, iterations=2):
        for _ in range(iterations):
            node = self.select()
            reward = self.simulate(node)
            self.backpropagation(node, reward)

            print(_ + 1, "iterations")
        return max(self.root.children, key=lambda n: n.visits).state.last_move

    def select(self):
        current = self.root
        while not current.state.is_terminal():
            if current.unexplored_actions:
                return current.expand()
            else:
                current = current.select_child()
        return current

    def simulate(self, node):
        current_state = node.state
        simulation_count = 2
        while not current_state.is_terminal() and simulation_count > 0:
            legal_actions = current_state.get_legal_actions()
            if not legal_actions:
                break

            action = random.choice(list(legal_actions))
            current_state = current_state.move(action)
            simulation_count -= 1
        return current_state.get_reward()

    def backpropagation(self, node, reward):
        while node:
            node.update(reward)
            node = node.parent
        return


class GameState:
    def __init__(self, last_move, board):
        self.last_move = last_move
        self.board = board

    def get_legal_actions(self):
        actions = defaultdict(set)

        visited = set()

        leaves_positions = set()

        all_directions = [
            Direction.Up,
            Direction.UpLeft,
            Direction.UpRight,
            Direction.Down,
            Direction.DownLeft,
            Direction.DownRight,
            Direction.Left,
            Direction.Right
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
            score = 1

            if isinstance(action, MoveAction):
                init_coord = action.coord
                final_coord = action.coord
                directions = action.directions

                for direction in directions:
                    final_coord += direction

                score = abs(final_coord.r - init_coord.r)

            actions[score].add(action)

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
                    if (self.board[route_coord].state in
                            (PlayerColor.RED, PlayerColor.BLUE) and
                            self.board[next_coord].state == 'LilyPad'):
                        new_direction = path + [direction]

                        if next_coord not in visited:
                            visited.add(next_coord)
                            jump_move(next_coord, new_direction, directions)
                            visited.remove(next_coord)
                except ValueError:
                    continue

        def grow_leaves(coord):
            for direction in all_directions:
                try:
                    next_coord = coord + direction
                    if self.board[next_coord].state is None:
                        leaves_positions.add(next_coord)
                except ValueError:
                    continue

            if leaves_positions:
                action = GrowAction()
                evaluate_action(action)

        match self.board.turn_color:
            case PlayerColor.RED:
                red_positions = []

                for coord, CellState in self.board._state.items():
                    if CellState.state == PlayerColor.RED:
                        red_positions.append(coord)

                for coord in red_positions:
                    normal_move(coord, red_directions)
                    jump_move(coord, [], red_directions)
                    grow_leaves(coord)

            case PlayerColor.BLUE:
                blue_positions = []

                for coord, CellState in self.board._state.items():
                    if CellState.state == PlayerColor.BLUE:
                        blue_positions.append(coord)

                for coord in blue_positions:
                    normal_move(coord, blue_directions)
                    jump_move(coord, [], blue_directions)
                    grow_leaves(coord)
        if actions:
            return actions[max(actions)]
        else:
            return None

    def move(self, action):
        legal_actions = self.get_legal_actions()
        if action not in legal_actions:
            raise ValueError(f"Illegal action: {action}")

        new_board = deepcopy(self.board)
        try:
            mutation = new_board.apply_action(action)
        except IllegalActionException as e:
            raise ValueError(f"Illegal action: {e}")
        return GameState(last_move=action, board=new_board)

    def is_terminal(self):
        return self.board.game_over

    def get_reward(self):

        def evaluate_heuristic():
            red_advance = self.board._row_count(PlayerColor.RED, BOARD_N - 1) / (BOARD_N - 2)
            blue_advance = self.board._row_count(PlayerColor.BLUE, 0) / (BOARD_N - 2)

            score = red_advance - blue_advance

            if self.board.turn_color == PlayerColor.RED:
                return score
            else:
                return -score

        if self.is_terminal():
            red_score = self.board._player_score(PlayerColor.RED)
            blue_score = self.board._player_score(PlayerColor.BLUE)

            if self.board.turn_color == PlayerColor.RED:
                return 1.0 if red_score > blue_score else \
                    (-1.0 if red_score < blue_score else 0.0)
            else:
                return 1.0 if blue_score > red_score else \
                    (-1.0 if blue_score < red_score else 0.0)

        else:
            return evaluate_heuristic()


if __name__ == '__main__':
    board = Board()
    initial_state = GameState(None, board)

    mcts = MCTS(initial_state)
    best_action = mcts.search(iterations=3)
    print("Best action:", best_action)