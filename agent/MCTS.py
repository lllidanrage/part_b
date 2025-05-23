# COMP30024 Artificial Intelligence, Semester 1 2025
# Project Part B: Game Playing Agent

import math
import random
import time
import sys
import os
from collections import defaultdict, deque 
from copy import deepcopy


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from referee.game import Direction, MoveAction, GrowAction, IllegalActionException, BOARD_N, Board, Coord, Action
from referee.game.player import PlayerColor
from referee.game.board import CellState


class Node:
    """
    A node in the Monte Carlo Tree Search tree.
    Each node represents a game state and maintains statistics for the MCTS algorithm.
    """
    __slots__ = ("state", "parent", "children", "total_rewards",
                "visits", "unexplored_actions")
                
    def __init__(self, state, parent=None):
        self.state = state
        self.parent = parent
        self.children = []
        self.total_rewards = 0.0  # Store as a single float, relative to root player
        self.visits = 0
        # GameState.get_legal_actions() returns a list sorted by priority (highest first)
        # Use deque for efficient pop from the left (highest priority)
        self.unexplored_actions = deque(state.get_legal_actions())

    def select_child(self, root_player_color):
        """
        Select the child with the highest UCB1 value.
        Rewards are relative to root_player_color.
        The decision at self (parent) is made by self.state.board.turn_color.
        """
        if not self.children:
            return self # Should not happen if called after ensuring children exist or unexplored_actions is empty
        
        exploration_constant = 1.414
        current_decision_maker_color = self.state.board.turn_color

        # Determine if the current decision maker is the same as the root player
        # If so, they want to maximize child.total_rewards (which is from root's perspective)
        # If not, they are the opponent, and want to minimize child.total_rewards (from root's perspective)
        exploitation_coeff = 1.0 if current_decision_maker_color == root_player_color else -1.0

        def ucb(child_node) -> float:
            """Calculate the UCB1 value for a child node with additional heuristic bonuses."""
            if child_node.visits == 0:
                return float('inf')
            
            # child_node.total_rewards is already relative to root_player_color
            exploitation_from_root_pov = child_node.total_rewards / child_node.visits
            effective_exploitation = exploitation_coeff * exploitation_from_root_pov
            
            exploration = exploration_constant * math.sqrt(math.log(self.visits) / child_node.visits)
            
            # Heuristic bonuses are from the perspective of current_decision_maker_color
            direction_bonus = 0.0
            center_bonus = 0.0
            action_to_child = child_node.state.last_move
            if action_to_child and isinstance(action_to_child, MoveAction):
                current_eval_pos = action_to_child.coord
                final_eval_coord = action_to_child.coord
                for jump_dir_segment in action_to_child.directions:
                    final_eval_coord = current_eval_pos + jump_dir_segment.value
                    current_eval_pos = final_eval_coord
                
                if len(action_to_child.directions) == 1:
                    direction = action_to_child.directions[0]
                    if current_decision_maker_color == PlayerColor.RED:
                        if direction in [Direction.Down, Direction.DownLeft, Direction.DownRight]: direction_bonus = 0.1
                    elif current_decision_maker_color == PlayerColor.BLUE:
                        if direction in [Direction.Up, Direction.UpLeft, Direction.UpRight]: direction_bonus = 0.1
                
                center_lower_bound = BOARD_N // 4
                center_upper_bound = BOARD_N - 1 - (BOARD_N // 4)
                is_horizontal_move = (action_to_child.coord.r == final_eval_coord.r)
                if not is_horizontal_move and \
                   (center_lower_bound <= final_eval_coord.r <= center_upper_bound and 
                    center_lower_bound <= final_eval_coord.c <= center_upper_bound):
                    center_bonus = 0.05
            return effective_exploitation + exploration + direction_bonus + center_bonus
        return max(self.children, key=ucb)

    def expand(self):
        """
        Expand the current node by adding a child node with an unexplored action.
        Returns the new child node or self if no expansion is possible.
        """
        if self.unexplored_actions:
            action = self.unexplored_actions.popleft()
            try:
                next_state = self.state.move(action)
                child = Node(next_state, parent=self)
                self.children.append(child)
                return child
            except ValueError: 
                return self.expand() 
        return self 

    def update(self, reward_increment_relative_to_root):
        """
        Update the node's statistics with a new reward.
        The reward is always from the perspective of the root player.
        """
        self.visits += 1
        self.total_rewards += reward_increment_relative_to_root


class MCTS:
    """
    Monte Carlo Tree Search implementation with action priorities.
    
    Action Priority Levels:
    1000: Priority 1  - Game-winning moves (reaching opponent's edge with non-starting piece)
    500:  Priority 2  - Single frog breakthrough (within 2 steps of goal line and moving forward)
    300:  Priority 3  - Multi-jump advance (row change >= 2 with forward jumps)
    200:  Priority 4  - Forward jumps with isolated pieces
    190:  Priority 5  - Opening phase: Jumps that significantly improve formation
    180:  Priority 6  - Opening phase: Moves that significantly improve formation
    160:  Priority 7  - Opening phase: Jumps that improve isolated piece cohesion
    150:  Priority 8  - Forward line push (normal forward jumps)
    140:  Priority 9  - Opening phase: Jumps with minor formation improvement
    130:  Priority 10 - Opening phase: Moves with minor formation improvement
    120:  Priority 11 - Opening phase: GROW actions that improve formation
    100:  Priority 12 - Bridge building (GROW actions creating jump opportunities)
    55:   Priority 13 - Blocking opponent (improving cohesion of isolated pieces in opening)
    50:   Priority 14 - Default GROW actions / Normal forward moves
    40:   Priority 15 - Self-blocking prevention
    30:   Priority 16 - Non-forward jumps with chain potential / Isolated piece moves improving cohesion
    20:   Priority 17 - Isolated piece moves
    10:   Priority 18 - Default actions
    1:    Priority 19 - Horizontal jumps without chain potential / Non-forward normal moves
    0.5:  Priority 20 - Goal line shuffling (piece already on goal line, moves to stay on it)
    """
    def __init__(self, state, use_minimax=True, minimax_depth=2, test_mode=False):
        self.root = Node(state)
        self.use_minimax = use_minimax
        self.minimax_depth = minimax_depth
        self.test_mode = test_mode
        self.root_player_color = state.board.turn_color

    def search(self, iterations: int = 50):
        """
        Perform Monte Carlo Tree Search for the specified number of iterations.
        Returns the best action found.
        """
        # Check for fixed opening moves
        if self.root.state.should_use_fixed_opening() and not self.test_mode:
            fixed_move = self.root.state.get_fixed_opening_move()
            if fixed_move is not None:
                # Increment fixed move counter for current color
                if self.root.state.board.turn_color == PlayerColor.RED:
                    self.root.state._red_fixed_moves += 1
                    self.root.state.board._red_fixed_moves = self.root.state._red_fixed_moves
                else:
                    self.root.state._blue_fixed_moves += 1
                    self.root.state.board._blue_fixed_moves = self.root.state._blue_fixed_moves

                self.root.state.last_move = fixed_move
                return fixed_move

        # Main MCTS loop
        for _ in range(iterations):
            leaf = self.select()
            if not leaf.unexplored_actions and not leaf.children and not leaf.state.is_terminal():
                # Handle potential dead-end states
                pass 
            
            if leaf.unexplored_actions and not leaf.state.is_terminal():
                child_leaf = leaf.expand()
                if child_leaf != leaf: 
                    sim_reward = self.simulate(child_leaf)
                    self.backpropagation(child_leaf, sim_reward)
                else: 
                    sim_reward = self.simulate(leaf) 
                    self.backpropagation(leaf, sim_reward)
            else:
                 sim_reward = self.simulate(leaf)
                 self.backpropagation(leaf, sim_reward)

        if not self.root.children:
            return None
        
        # Debug: Print root children statistics
        print("\n--- Root Children Stats ---")
        for child in self.root.children:
            act = child.state.last_move
            if child.visits > 0:
                mean_reward = child.total_rewards / child.visits
            else:
                mean_reward = 0.0 
            print(f"{str(act):<40}  visits={child.visits:<3}  mean_reward={mean_reward:+.3f}")
        print("---------------------------")

        # Select best child based on average reward
        best_child = max(self.root.children, 
                         key=lambda n: n.total_rewards / (n.visits or 1))
        return best_child.state.last_move

    def select(self):
        """
        Select a leaf node using the UCB1 formula.
        Returns either:
        1. A non-terminal node with unexplored actions
        2. A terminal node
        3. A non-terminal node that couldn't expand (rare edge case)
        """
        current = self.root
        while not current.state.is_terminal():
            if current.unexplored_actions:
                return current 
            elif not current.children: 
                return current
            else:
                current = current.select_child(self.root_player_color)
        return current

    def simulate(self, node):
        """
        Simulate a game from the given node until terminal state or simulation limit.
        Uses either Minimax or random simulation based on configuration.
        """
        if self.use_minimax:
            return self.minimax_simulation(node.state, self.minimax_depth)
        else:
            return self.random_simulation(node.state)
    
    def minimax_simulation(self, state, depth):
        """
        Perform a Minimax simulation with alpha-beta pruning.
        Uses action priorities to focus on promising moves.
        """
        legal_actions_set = state.get_legal_actions()
        if not legal_actions_set:
            return state.get_reward()
            
        # Convert action set to list and evaluate priorities
        legal_actions = []
        action_priorities = {}
        
        for action in legal_actions_set:
            priority = 1  # Default lowest priority
            
            if isinstance(action, MoveAction):
                init_coord = action.coord
                directions = action.directions
                final_coord = init_coord
                
                for direction in directions:
                    final_coord += direction
                
                # Priority 1: Game-winning moves
                if ((state.board.turn_color == PlayerColor.RED and final_coord.r == BOARD_N - 1) or
                    (state.board.turn_color == PlayerColor.BLUE and final_coord.r == 0)):
                    priority = 1000
                    
                # Priority 2: Single frog breakthrough
                distance_to_goal = 0
                if state.board.turn_color == PlayerColor.RED:
                    distance_to_goal = BOARD_N - 1 - init_coord.r
                    if distance_to_goal <= 2 and final_coord.r > init_coord.r:
                        priority = max(priority, 500)
                else:  # BLUE
                    distance_to_goal = init_coord.r
                    if distance_to_goal <= 2 and final_coord.r < init_coord.r:
                        priority = max(priority, 500)
                
                # Calculate piece cohesion scores
                try:
                    current_cohesion = self._calculate_cohesion_score(state, state.board.turn_color, init_coord)
                    final_cohesion = self._calculate_cohesion_score(state, state.board.turn_color, final_coord)
                    
                    is_isolated = current_cohesion < 0.3
                    improves_cohesion = final_cohesion > current_cohesion
                except:
                    is_isolated = False
                    improves_cohesion = False
                
                row_change = abs(final_coord.r - init_coord.r)
                
                # Check if move is forward
                is_forward = False
                if ((state.board.turn_color == PlayerColor.RED and final_coord.r > init_coord.r) or
                    (state.board.turn_color == PlayerColor.BLUE and final_coord.r < init_coord.r)):
                    is_forward = True
                
                # Analyze jump moves
                is_jump = False
                jump_target = None
                if len(directions) == 1:
                    direction = directions[0]
                    next_coord = init_coord + direction
                    try:
                        if state.board[next_coord].state in (PlayerColor.RED, PlayerColor.BLUE):
                            jump_target = next_coord + direction
                            if (jump_target.r >= 0 and jump_target.r < BOARD_N and 
                                jump_target.c >= 0 and jump_target.c < BOARD_N and
                                state.board[jump_target].state == "LilyPad"):
                                is_jump = True
                    except (ValueError, IndexError, KeyError, AttributeError):
                        pass
                
                if is_jump:
                    if is_forward:
                        # Priority 3: Multi-jump advance
                        if row_change >= 2:
                            priority = max(priority, 300)
                        elif is_isolated and improves_cohesion:
                            # Priority 4: Forward jumps with isolated pieces
                            priority = max(priority, 120)
                        else:
                            # Priority 8: Forward line push
                            priority = max(priority, 150)
                    else:
                        # Analyze chain jump potential
                        has_chain_potential = False
                        
                        if jump_target:
                            forward_directions = []
                            if state.board.turn_color == PlayerColor.RED:
                                forward_directions = [Direction.Down, Direction.DownLeft, Direction.DownRight]
                            else:  # BLUE
                                forward_directions = [Direction.Up, Direction.UpLeft, Direction.UpRight]
                                
                            for next_dir in forward_directions:
                                try:
                                    next_jump_over = jump_target + next_dir
                                    if (0 <= next_jump_over.r < BOARD_N and 
                                        0 <= next_jump_over.c < BOARD_N and
                                        state.board[next_jump_over].state in (PlayerColor.RED, PlayerColor.BLUE)):
                                        
                                        next_jump_target = next_jump_over + next_dir
                                        if (0 <= next_jump_target.r < BOARD_N and 
                                            0 <= next_jump_target.c < BOARD_N and
                                            state.board[next_jump_target].state == "LilyPad"):
                                            
                                            has_chain_potential = True
                                            break
                                except (ValueError, IndexError, KeyError, AttributeError):
                                    continue
                        
                        if is_isolated and improves_cohesion:
                            # Priority 16: Isolated piece moves improving cohesion
                            priority = max(priority, 30)
                        elif has_chain_potential:
                            # Priority 16: Non-forward jumps with chain potential
                            priority = max(priority, 30)
                else:
                    # Handle non-jump moves
                    if is_forward:
                        if is_isolated and improves_cohesion:
                            # Priority 16: Isolated piece moves improving cohesion
                            priority = max(priority, 30)
                        else:
                            priority = max(priority, 1)  # Default priority
                    
            elif isinstance(action, GrowAction):
                # Priority 14: Default GROW actions
                priority = 55
            
            action_priorities[action] = priority
            legal_actions.append(action)
        
        # Sort actions by priority
        sorted_actions = sorted(legal_actions, key=lambda a: action_priorities[a], reverse=True)
        
        # Consider only top priority actions for performance
        max_actions_to_consider = 12
        pruned_actions = sorted_actions[:max_actions_to_consider]
        
        # Perform Minimax search
        return self.minimax(state, min(depth, 3), float('-inf'), float('inf'), True, pruned_actions)
        
    def minimax(self, state, depth, alpha, beta, maximizing_player, priority_actions=None):
        """
        Minimax algorithm with alpha-beta pruning.
        Optionally considers only priority actions for better performance.
        """
        if depth == 0 or state.is_terminal():
            return state.get_reward()
        
        if priority_actions is not None and priority_actions:
            actions_to_consider = priority_actions
        else:
            legal_actions_set = state.get_legal_actions()
            if not legal_actions_set:
                return state.get_reward()
            
            actions_to_consider = []
            for action in legal_actions_set:
                actions_to_consider.append(action)
        
        if maximizing_player:
            value = float('-inf')
            for action in actions_to_consider:
                try:
                    next_state = state.move(action)
                    new_value = self.minimax(next_state, depth - 1, alpha, beta, False)
                    value = max(value, new_value)
                    alpha = max(alpha, value)
                    if beta <= alpha:
                        break  # Beta pruning
                except Exception:
                    continue
            return value
        else:
            value = float('inf')
            for action in actions_to_consider:
                try:
                    next_state = state.move(action)
                    new_value = self.minimax(next_state, depth - 1, alpha, beta, True)
                    value = min(value, new_value)
                    beta = min(beta, value)
                    if beta <= alpha:
                        break  # Alpha pruning
                except Exception:
                    continue
            return value
    
    def random_simulation(self, state):
        """
        Perform a random simulation from the given state.
        Uses action priorities to guide the simulation.
        """
        current_state = state
        simulation_count = 8
        for _ in range(simulation_count):
            if current_state.is_terminal(): break
            legal_actions_list = current_state.get_legal_actions()
            if not legal_actions_list: break
            action_to_simulate = random.choice(legal_actions_list)
            try:
                current_state = current_state.move(action_to_simulate)
            except ValueError: 
                break 
        return current_state.get_reward()

    def backpropagation(self, node, reward_from_sim_leaf_pov):
        """
        Backpropagate the simulation result through the tree.
        Converts rewards to be relative to the root player's perspective.
        """
        sim_leaf_player_color = node.state.board.turn_color
        
        if sim_leaf_player_color == self.root_player_color:
            reward_relative_to_root = reward_from_sim_leaf_pov
        else:
            reward_relative_to_root = -reward_from_sim_leaf_pov
            
        current_node = node
        while current_node:
            if current_node.parent:
                current_node.update(reward_relative_to_root)
            else:
                current_node.visits += 1
            current_node = current_node.parent


# Constants for jump directions
ALL_DIRECTIONS_ORDERED = [
    Direction.Up, Direction.Down, Direction.Left, Direction.Right,
    Direction.UpLeft, Direction.UpRight, Direction.DownLeft, Direction.DownRight
]
LEGAL_JUMP_DIRECTIONS_RED = tuple(d for d in ALL_DIRECTIONS_ORDERED if d not in {Direction.Up, Direction.UpRight, Direction.UpLeft})
LEGAL_JUMP_DIRECTIONS_BLUE = tuple(d for d in ALL_DIRECTIONS_ORDERED if d not in {Direction.Down, Direction.DownRight, Direction.DownLeft})

def _clone_board_mcts_version(board_to_clone: Board) -> Board:
    """
    Create a deep copy of a game board for MCTS simulation.
    Preserves all necessary state including fixed opening move counters.
    """
    new_board = Board(initial_player=board_to_clone.turn_color)

    new_board._state = {
        coord: CellState(cell.state)
        for coord, cell in board_to_clone._state.items()
    }

    new_board._history = list(board_to_clone._history)

    new_board._red_fixed_moves = board_to_clone._red_fixed_moves
    new_board._blue_fixed_moves = board_to_clone._blue_fixed_moves
    
    return new_board

class GameState:
    """
    Represents the complete state of a game at a particular point.
    Includes the board state and additional information needed for MCTS.
    """
    def __init__(self, last_move, board, test_mode=False):
        self.board = board
        self.last_move = last_move
        self.test_mode = test_mode
        self.my_frogs = []
        self._update_my_frogs()
        
        # Initialize fixed opening move counters if not present
        if not hasattr(self.board, '_red_fixed_moves'):
            self.board._red_fixed_moves = 0
        if not hasattr(self.board, '_blue_fixed_moves'):
            self.board._blue_fixed_moves = 0
            
        # Local copies for tracking fixed opening moves
        self._red_fixed_moves = self.board._red_fixed_moves
        self._blue_fixed_moves = self.board._blue_fixed_moves

    def _get_bit(self, coord: Coord) -> int:
        if 0 <= coord.r < BOARD_N and 0 <= coord.c < BOARD_N:
            return 1 << (coord.r * BOARD_N + coord.c)
        return 0

    def _get_initial_occupied_bitmask(self) -> int:
        mask = 0
        for r_idx in range(BOARD_N):
            for c_idx in range(BOARD_N):
                coord = Coord(r_idx, c_idx)
                cell_state = self.board[coord].state
                if cell_state == PlayerColor.RED or cell_state == PlayerColor.BLUE:
                    mask |= self._get_bit(coord)
        return mask

    def _is_frog_at(self, coord: Coord, occupied_mask: int) -> bool:
        if not (0 <= coord.r < BOARD_N and 0 <= coord.c < BOARD_N):
            return False
        return bool(occupied_mask & self._get_bit(coord))

    def _is_lilypad_empty_at(self, coord: Coord, occupied_mask: int) -> bool:
        if not (0 <= coord.r < BOARD_N and 0 <= coord.c < BOARD_N):
            return False
        # Check original board for LilyPad, and current mask for emptiness
        return self.board[coord].state == "LilyPad" and not (occupied_mask & self._get_bit(coord))

    def _enumerate_jumps(self, start_coord: Coord, player_color: PlayerColor) -> set[MoveAction]:
        """
        Find all possible jump sequences from a given starting coordinate.
        Uses depth-first search to find all valid jump combinations.
        """
        results = set()
        initial_mask = self._get_initial_occupied_bitmask()
        
        stack = [(start_coord, [], initial_mask, {start_coord})]
        
        jump_directions = LEGAL_JUMP_DIRECTIONS_RED if player_color == PlayerColor.RED else LEGAL_JUMP_DIRECTIONS_BLUE

        while stack:
            current_pos, current_path_dirs, current_mask, visited_landings = stack.pop()
            jumped_further_in_this_step = False
            for direction in jump_directions:
                    dr, dc = direction.value.r, direction.value.c # Direction increments
                    
                    # Calculate integer coordinates first
                    r_over, c_over = current_pos.r + dr, current_pos.c + dc
                    r_land, c_land = r_over + dr, c_over + dc

                    # Pre-check bounds for the landing coordinate
                    # If land_coord is out of bounds, skip this direction
                    if not (0 <= r_land < BOARD_N and 0 <= c_land < BOARD_N):
                        continue
                    
                    # If landing coordinates are valid, then over_coord's raw coordinates must also be valid.
                    # Now it's safe to construct Coord objects.
                    over_coord = Coord(r_over, c_over)
                    land_coord = Coord(r_land, c_land)
                    
                    if land_coord in visited_landings:
                        continue
                    
                    if self._is_frog_at(over_coord, current_mask) and \
                       self._is_lilypad_empty_at(land_coord, current_mask):
                        
                        jumped_further_in_this_step = True
                        new_path_dirs = current_path_dirs + [direction]
                        
                        updated_mask = current_mask
                        updated_mask &= ~self._get_bit(current_pos) 
                        updated_mask &= ~self._get_bit(over_coord) 
                        updated_mask |= self._get_bit(land_coord)  
                        
                        new_visited_landings = visited_landings | {land_coord}
                        stack.append((land_coord, new_path_dirs, updated_mask, new_visited_landings))
            
            if not jumped_further_in_this_step and len(current_path_dirs) >= 1:
                results.add(MoveAction(start_coord, tuple(current_path_dirs)))
        return results

    def _update_my_frogs(self):
        """Update the list of frogs belonging to the current player."""
        self.my_frogs = []
        for r in range(BOARD_N):
            for c in range(BOARD_N):
                coord = Coord(r, c)
                if self.board[coord].state == self.board.turn_color:
                    self.my_frogs.append(coord)

    def is_opening_phase(self):
        """Check if the game is still in the opening phase (first 30 turns)."""
        return self.board.turn_count < 30
        
    def should_use_fixed_opening(self):
        """
        Determine if fixed opening moves should be used.
        Returns True if within first 15 turns and player hasn't used all fixed moves.
        """
        if self.test_mode:
            return False
        if self.board.turn_count < 15:
            if self.board.turn_color == PlayerColor.RED and self._red_fixed_moves < 5:
                return True
            elif self.board.turn_color == PlayerColor.BLUE and self._blue_fixed_moves < 5:
                return True
        return False
        
    def get_fixed_opening_move(self):
        """
        Return the next fixed opening move for the current player.
        Returns None if no fixed move is available.
        """
        if self.board.turn_color == PlayerColor.RED:
            if self._red_fixed_moves == 0: return MoveAction(Coord(0, 2), (Direction.Down,))
            elif self._red_fixed_moves == 1: return MoveAction(Coord(0, 5), (Direction.Down,))
            elif self._red_fixed_moves == 2: return GrowAction()
            elif self._red_fixed_moves == 3: return MoveAction(Coord(0,1), (Direction.DownRight,))
            elif self._red_fixed_moves == 4: return MoveAction(Coord(0, 6), (Direction.DownLeft,))
        else:
            if self._blue_fixed_moves == 0: return MoveAction(Coord(7, 2), (Direction.Up,))
            elif self._blue_fixed_moves == 1: return MoveAction(Coord(7, 5), (Direction.Up,))
            elif self._blue_fixed_moves == 2: return GrowAction()
            elif self._blue_fixed_moves == 3: return MoveAction(Coord(7,1), (Direction.UpRight,))
            elif self._blue_fixed_moves == 4: return MoveAction(Coord(7, 6), (Direction.UpLeft,))
        return None

    def get_legal_actions(self) -> list[Action]:
        """
        Get all legal actions for the current state.
        Returns a list of actions sorted by priority (highest first).
        """
        if self.should_use_fixed_opening() and not self.test_mode:
            fixed_move = self.get_fixed_opening_move()
            if fixed_move is not None: return [fixed_move]
        
        prioritized_actions_tuples = []
        current_player_color = self.board.turn_color

        for coord in self.my_frogs:
            is_at_goal_line = False
            if current_player_color == PlayerColor.RED and coord.r == BOARD_N - 1:
                is_at_goal_line = True
            elif current_player_color == PlayerColor.BLUE and coord.r == 0:
                is_at_goal_line = True

            # Generate Sliding Moves
            for direction in ALL_DIRECTIONS_ORDERED:
                slide_action = MoveAction(coord, (direction,))
                try:
                    self.board._validate_move_action(slide_action) 
                    final_slide_coord = coord + direction.value
                    is_forward_slide = False
                    if current_player_color == PlayerColor.RED:
                        if final_slide_coord.r > coord.r: is_forward_slide = True
                    else: 
                        if final_slide_coord.r < coord.r: is_forward_slide = True
                    
                    current_slide_priority = 1
                    if is_at_goal_line:
                        current_slide_priority = 0.5  # Lower priority for moves on goal line
                    else:
                        # Check if near goal line
                        is_near_goal = False
                        target_coord = coord + direction.value
                        if current_player_color == PlayerColor.RED and coord.r == BOARD_N - 2:  # Red's 6th row
                            if self.board[target_coord].state == "LilyPad":  # Moving to goal on lily pad
                                is_near_goal = True
                        elif current_player_color == PlayerColor.BLUE and coord.r == 1:  # Blue's 1st row
                            if self.board[target_coord].state == "LilyPad":  # Moving to goal on lily pad
                                is_near_goal = True
                        
                        if is_near_goal:
                            current_slide_priority = 55  # Higher priority for moves near goal
                        else:
                            current_slide_priority = 55 if is_forward_slide else 1
                    prioritized_actions_tuples.append((current_slide_priority, slide_action))
                except IllegalActionException:
                    pass 

            # Generate Jump Moves
            jump_actions_for_frog = self._enumerate_jumps(coord, current_player_color)
            for jump_action in jump_actions_for_frog:
                num_segments = len(jump_action.directions)
                current_pos_for_calc = coord 
                final_jump_coord = coord 
                for jump_dir_segment in jump_action.directions:
                    land_coord = current_pos_for_calc + jump_dir_segment.value + jump_dir_segment.value
                    final_jump_coord = land_coord 
                    current_pos_for_calc = land_coord 

                if is_at_goal_line:
                    current_jump_priority = 0.5  # Lower priority for jumps on goal line
                else:
                    is_forward_jump = False
                    if current_player_color == PlayerColor.RED:
                        if final_jump_coord.r > coord.r: is_forward_jump = True
                    else: 
                        if final_jump_coord.r < coord.r: is_forward_jump = True
                    
                    row_change = abs(final_jump_coord.r - coord.r)
                    if num_segments >= 2:
                        if is_forward_jump and row_change >= 2: current_jump_priority = 300 
                        elif is_forward_jump: current_jump_priority = 250 
                        else: current_jump_priority = 100 
                    elif num_segments == 1:
                        if is_forward_jump: current_jump_priority = 150 
                        else: current_jump_priority = 20
                prioritized_actions_tuples.append((current_jump_priority, jump_action))

        # Check if GROW action is available
        current_player_frogs_count = 0
        has_empty_lilypad = False
        
        for r_idx in range(BOARD_N):
            for c_idx in range(BOARD_N):
                cell_coord = Coord(r_idx, c_idx)
                cell_state_obj = self.board[cell_coord]
                if cell_state_obj.state == current_player_color:
                    current_player_frogs_count += 1
                if cell_state_obj.state == "LilyPad": 
                    has_empty_lilypad = True
        
        if current_player_frogs_count < BOARD_N and has_empty_lilypad:
            prioritized_actions_tuples.append((50, GrowAction()))
        
        # Sort actions by priority and extract the actions
        prioritized_actions_tuples.sort(key=lambda x: x[0], reverse=True)
        sorted_actions = [action for priority, action in prioritized_actions_tuples]
        
        return sorted_actions if sorted_actions else [GrowAction()] # Ensure at least GROW if nothing else

    def _check_chain_jump_potential(self, coord): 
        return False # Obsolete, _enumerate_jumps handles this

    def move(self, action):
        """
        Apply an action to the current state and return a new state.
        Raises ValueError if the action is illegal.
        """
        new_board = _clone_board_mcts_version(self.board)
        try:
            new_board.apply_action(action)
            new_state = GameState(action, new_board, self.test_mode)
            return new_state 
        except IllegalActionException as e:
            raise ValueError(f"Illegal action: {e}") from e

    def is_terminal(self):
        """Check if the current state is a terminal state."""
        return self.board.game_over

    def get_reward(self):
        """
        Calculate the reward value for the current state.
        Returns a high positive/negative value for terminal states,
        otherwise returns a heuristic evaluation.
        """
        if self.is_terminal():
            red_score = self.board._player_score(PlayerColor.RED)
            blue_score = self.board._player_score(PlayerColor.BLUE)
            if self.board.turn_color == PlayerColor.RED:
                return 1000.0 if red_score > blue_score else (-1000.0 if red_score < blue_score else 0.0)
            else:
                return 1000.0 if blue_score > red_score else (-1000.0 if blue_score < red_score else 0.0)
        score = 0.0
        red_goal_count = self.board._row_count(PlayerColor.RED, BOARD_N - 1)
        blue_goal_count = self.board._row_count(PlayerColor.BLUE, 0)
        score += 5.0 * (red_goal_count - blue_goal_count)
        return score if self.board.turn_color == PlayerColor.RED else -score

    def _calculate_cohesion_score(self, player_color, piece_coord):
        """
        Calculate how well a piece is connected with other friendly pieces.
        Returns a score between 0 and 1, where 1 indicates perfect cohesion.
        """
        cohesion_score = 0
        ally_pieces = []
        for coord_ally, cell_ally in self.board._state.items():
            if cell_ally.state == player_color and coord_ally != piece_coord:
                ally_pieces.append(coord_ally)
        if not ally_pieces: return 0
        total_distance = sum(abs(piece_coord.r - ac.r) + abs(piece_coord.c - ac.c) for ac in ally_pieces)
        avg_distance = total_distance / len(ally_pieces)
        return 1.0 - (avg_distance / (2 * BOARD_N))

    def _check_jump_bridge_formation(self, player_color, target_coord):
        """
        Check if a move creates or maintains a bridge formation for jumps.
        Currently a placeholder for future implementation.
        """
        return 0


if __name__ == '__main__':
    #just for testing
    basic_board = Board()
    

    new_board = Board()
    
    
    for r in range(BOARD_N):
        for c in range(BOARD_N):
            coord = Coord(r, c)
            empty_cell = None
            for test_r in range(BOARD_N):
                for test_c in range(BOARD_N):
                    test_coord = Coord(test_r, test_c)
                    if test_coord in new_board._state and new_board._state[test_coord].state is None:
                        empty_cell = new_board._state[test_coord]
                        break
                if empty_cell:
                    break
            if empty_cell:
                new_board.set_cell_state(coord, empty_cell)
    

    red_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == PlayerColor.RED:
            red_cell = cell
            break
    
    red_coord = Coord(2, 2)
    if red_cell:
        new_board.set_cell_state(red_coord, red_cell)
    

    blue_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == PlayerColor.BLUE:
            blue_cell = cell
            break
            
    blue_coord = Coord(3, 3)
    if blue_cell:
        new_board.set_cell_state(blue_coord, blue_cell)
    

    lily_cell = None
    for coord, cell in basic_board._state.items():
        if cell.state == "LilyPad":
            lily_cell = cell
            break
            
    lily_coord = Coord(4, 4)
    if lily_cell:
        new_board.set_cell_state(lily_coord, lily_cell)
    

    new_board.set_turn_color(PlayerColor.RED)
    
    print("=== 测试跳跃功能 ===")
    print("初始棋盘:")
    print(new_board.render())
    
    state = GameState(None, new_board, test_mode=True)
    legal_actions = state.get_legal_actions()
    print(f"合法动作: {legal_actions}")
    
    print("\n===== MCTS-Minimax混合算法 =====")
    start_time = time.time()
    mcts = MCTS(state, use_minimax=True, minimax_depth=2, test_mode=True)
    best_action = mcts.search(iterations=30)
    minimax_time = time.time() - start_time
    print(f"耗时: {minimax_time:.2f}秒")
    print(f"最佳动作: {best_action}")
    
    print("\n===== 传统MCTS算法 =====")
    start_time = time.time()
    mcts_traditional = MCTS(state, use_minimax=False, test_mode=True)
    best_action_traditional = mcts_traditional.search(iterations=30)
    traditional_time = time.time() - start_time
    print(f"耗时: {traditional_time:.2f}秒")
    print(f"最佳动作: {best_action_traditional}")

