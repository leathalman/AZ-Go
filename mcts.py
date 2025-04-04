import copy
import math
import sys

import numpy as np

from definitions import CONFIG_PATH
from utils.config_handler import ConfigHandler


class MCTS:
    """
    This class handles the MCTS tree.
    """

    def get_stack_size(self):
        size = 2  # current frame and caller's frame always exist
        while True:
            try:
                sys._getframe(size)
                size += 1
            except ValueError:
                return size - 1  # subtract current frame

    def __init__(self, game, nnet, is_self_play, config=None):
        self.game = game
        self.nnet = nnet
        self.is_self_play = is_self_play

        # added for compatibility with Pyinstaller
        if config is None:
            self.config = ConfigHandler(CONFIG_PATH)
        else:
            self.config = config

        self.Qsa = {}  # stores Q values for s,a (as defined in the paper)
        self.Nsa = {}  # stores #times edge s,a was visited
        self.Ns = {}  # stores #times board s was visited
        self.Ps = {}  # stores initial policy (returned by neural net)
        self.smartSimNum = 10 * (self.game.getBoardSize()[0] ** 2)
        self.Es = {}  # stores game.getGameEnded ended for board s
        self.Ss = {} # stores the score for board s
        self.Vs = {}  # stores game.getValidMoves for board s

    def getActionProb(self, board, canonicalBoard, canonicalHistory, x_boards, y_boards, player_board, num_sims, temp=1):
        """
        This function performs numMCTSSims simulations of MCTS starting from
        canonicalBoard.

        Returns:
            probs: a policy vector where the probability of the ith action is
                   proportional to Nsa[(s,a)]**(1./temp)
        """
        # removed min(num_MCTS_sims, smartsimnum)
        for i in range(num_sims):
            self.search(board, canonicalBoard, canonicalHistory, x_boards, y_boards, player_board, 1, True)

        s = self.game.stringRepresentation(canonicalBoard, is_canonical=True)

        counts = np.array([self.Nsa[(s, a)] if (s, a) in self.Nsa else 0 for a in range(self.game.getActionSize())])
        valids = self.game.getValidMoves(board)
        self.smartSimNum = 10 * (np.count_nonzero(valids))

        if np.sum(counts) == 0:
            counts = valids
        else:
            counts *= valids
            # temporary fix
            if np.sum(counts) == 0:
                counts = valids
                print("MCTS counts & valids error occurred.")

        if temp == 0:
            bestA = np.argmax(counts)
            try:
                assert (valids[bestA] != 0)
            except:
                print("temp=0, assert valids[bestA]!=0 !!!")
                print("current valids:", valids)
                flag_Qsa = False
                flag_Nsa = False
                if s in self.Ps:
                    print("s in p! Which measn it's been visited, has the probability of each action", self.Ps[s])
                for _ in range(self.game.getActionSize()):
                    if (s, _) in self.Nsa:
                        print(_, "in Nsa! which measn its value is calculated to ", self.Nsa[(s, _)])
                    else:
                        flag_Nsa = True
                        print(_, "no Nsa value, set 0 by default in counts=[...]!")

                    if (s, _) in self.Qsa:
                        print(_, "in! Qsa with value:", self.Qsa[(s, _)])
                    else:
                        flag_Qsa = True
                        print(_, "no Qsa value")

                    if flag_Nsa and flag_Qsa:
                        print("no nsa, no qsa")
                    if flag_Nsa and not flag_Qsa:
                        print("no nsa, has qsa")
                    if not flag_Nsa and flag_Qsa:
                        print("has nsa, no qsa")

                # print(counts)
            # print(counts)
            probs = [0 for i in range(len(counts))]
            probs[bestA] = 1

            # Unmasking code
            # Get full move "probabilities" instead of masking
            # probs = [x / float(sum(counts)) for x in counts]

            for _ in range(self.game.getActionSize()):
                if probs[_] > 0:
                    assert (valids[_] > 0)

            # Unmasking code
            # return probs * valids
            return probs

        counts = [x ** (1. / temp) for x in counts]
        # print(f"COUNTS: {counts}")
        probs = [x / float(sum(counts)) for x in counts]

        for _ in range(self.game.getActionSize()):
            if probs[_] > 0:
                assert (valids[_] > 0)

        return probs * valids

    def search(self, board, canonicalBoard, canonicalHistory, x_boards, y_boards, player_board, calls, is_root):
        """
        This function performs one iteration of MCTS. It is recursively called
        till a leaf node is found. The action chosen at each node is one that
        has the maximum upper confidence bound as in the paper.

        Once a leaf node is found, the neural network is called to return an
        initial policy P and a value v for the state. This value is propogated
        up the search path. In case the leaf node is a terminal state, the
        outcome is propogated up the search path. The values of Ns, Nsa, Qsa are
        updated.

        NOTE: the return values are the negative of the value of the current
        state. This is done since v is in [-1,1] and if v is the value of a
        state for the current player, then its value is -v for the other player.

        Returns:
            v: the negative of the value of the current canonicalBoard
        """

        # check if both players passed
        """if len(canonicalBoard.history) > 1:
            if canonicalBoard.history[-1] is None and canonicalBoard.history[-2] is None:
                if 1 in player_board[0]:
                    perspective = 1
                else:
                    perspective = -1
                gameEnd = self.game.getGameEndedArena(canonicalBoard, perspective)
                # print("Ended sim with back to back passes after ", calls, " calls with reward -- ", gameEnd)
                if gameEnd != 0:
                    return -gameEnd
                else:
                    return 0"""
        # See if game is in a terminal state
        # NOTE: Changed string representation call!
        # s = self.game.stringRepresentation(canonicalBoard)
        s = self.game.stringRepresentation(canonicalBoard, is_canonical=True)
        non_canonical_s = self.game.stringRepresentation(board, is_canonical=False)

        if s not in self.Es:
                # self.Es[s], self.Ss[non_canonical_s] = self.game.getGameEndedSelfPlay(board, True, self)
                self.Es[s], self.Ss[non_canonical_s] = self.game.getGameEndedArena(board, True, None, None)
        if self.Es[s] != 0:
            return -self.Es[s]

        # See if recursion limit has been reached
        if calls > 500:
            return 1e-4

        # Get current game history if terminal state not found
        if calls > 1:
            canonicalHistory, x_boards, y_boards = self.game.getCanonicalHistory(copy.deepcopy(x_boards),
                                                                                 copy.deepcopy(y_boards),
                                                                                 canonicalBoard, player_board)

        # If current state is a leaf node, add this to the tree
        if s not in self.Ps:
            # print("leaf node")
            if self.is_self_play:
                self.Ps[s], v = self.nnet.predict(canonicalHistory)  # changed from board.pieces
            else:
                self.Ps[s], v = self.predict(board)  # changed from board.pieces
            valids = self.game.getValidMoves(board)
            self.Ps[s] = self.Ps[s] * valids  # masking invalid moves
            sum_Ps_s = np.sum(self.Ps[s])
            if sum_Ps_s > 0:
                self.Ps[s] /= sum_Ps_s  # renormalize
            else:
                # if all valid moves were masked make all valid moves equally probable

                # NB! All valid moves may be masked if either your NNet architecture is insufficient or you've get overfitting or something else.
                # If you have got dozens or hundreds of these messages you should pay attention to your NNet and/or training process.
                self.Ps[s] = self.Ps[s] + valids
                self.Ps[s] /= np.sum(self.Ps[s])

            self.Vs[s] = valids
            self.Ns[s] = 0

            # do not use score threshold in MCTS
            if s not in self.Es:
                # self.Es[s], self.Ss[non_canonical_s] = self.game.getGameEndedSelfPlay(board, True, self)
                self.Es[s], self.Ss[non_canonical_s] = self.game.getGameEndedArena(board, True, None, None)
                gameEnd = self.Es[s]
            else:
                gameEnd = self.Es[s]
            if gameEnd != 0:
                return -gameEnd
            return -v

        # Current state is not a leaf node
        valids = self.Vs[s]
        cur_best = -float('inf')
        best_act = -1
        # pick the action with the highest upper confidence bound
        # add noise for root node prior probabilities (encourages exploration)
        if is_root and self.is_self_play:
            noise = np.random.dirichlet([0.03] * len(self.game.filter_valid_moves(valids)))

        i = -1
        for a in range(self.game.getActionSize()):
            if valids[a] != 0:
                i += 1
                if (s, a) in self.Qsa and self.Qsa[(s, a)] != None:
                    q = self.Qsa[(s, a)]
                    n_sa = self.Nsa[(s, a)]
                    """u = self.Qsa[(s, a)] + self.config["c_puct"] * self.Ps[s][a] * math.sqrt(self.Ns[s]) / (
                                1 + self.Nsa[(s, a)])"""
                else:
                    q = 0
                    n_sa = 0
                    # u = self.config["c_puct"] * self.Ps[s][a] * math.sqrt(self.Ns[s])  # Q = 0 ?

                p = self.Ps[s][a]
                # add noise for root node prior probabilities (encourages exploration)
                if is_root and self.is_self_play:
                    p = (1 - 0.25) * p + 0.25 * noise[i]
                u = q + self.config["c_puct"] * p * math.sqrt(self.Ns[s]) / (1 + n_sa)
                if u > cur_best:
                    cur_best = u
                    best_act = a

        a = best_act
        """if a == 49:
            print("-------------Passed on call #", calls, "------------------")
            print("Valids used to pass: ", valids)
            print("Probs used to pass: ", self.Ps[s])"""
        assert (valids[a] != 0)
        # print("in MCTS.search, need next search, shifting player from 1")

        try:
            next_s = self.game.getNextState(board, a)
            # print("in MCTS.search, need next search, next player is {}".format(next_player))
        except:
            # print("###############在search内部节点出现错误：###########")
            # print("action:{},valids:{},Vs:{}".format(a,valids,self.Vs[s]))
            valids = self.game.getValidMoves(board)
            self.Vs[s] = valids
            cur_best = -float('inf')
            best_act = -1

            if is_root and self.is_self_play:
                noise = np.random.dirichlet([0.03] * len(self.game.filter_valid_moves(valids)))

            i = -1
            for a in range(self.game.getActionSize()):
                if valids[a] != 0:
                    i += 1
                    if (s, a) in self.Qsa and self.Qsa[(s, a)] != None:
                        q = self.Qsa[(s, a)]
                        n_sa = self.Nsa[(s, a)]
                        """u = self.Qsa[(s, a)] + self.config["c_puct"] * self.Ps[s][a] * math.sqrt(self.Ns[s]) / (
                                    1 + self.Nsa[(s, a)])"""
                    else:
                        q = 0
                        n_sa = 0
                        # u = self.config["c_puct"] * self.Ps[s][a] * math.sqrt(self.Ns[s])  # Q = 0 ?

                    p = self.Ps[s][a]
                    if is_root and self.is_self_play:
                        p = (1 - 0.25) * p + 0.25 * noise[i]
                    u = q + self.config["c_puct"] * p * math.sqrt(self.Ns[s]) / (1 + n_sa)
                    if u > cur_best:
                        cur_best = u
                        best_act = a

            a = best_act
            # print("recalculate the valids vector:{} ".format(valids))
            # try:
            next_s = self.game.getNextState(board, a)
            # except:
            #     print(f"RETURNING Exception -- Tried Action {a}")
            #     return

        next_s_canonical = self.game.getCanonicalForm(next_s, next_s.current_player)

        if 1 in player_board[0]:
            player_board = (np.zeros((7, 7)), np.ones((7, 7)))
        else:
            player_board = (np.ones((7, 7)), np.zeros((7, 7)))

        calls += 1
        x_boards, y_boards = y_boards, x_boards

        v = self.search(next_s, next_s_canonical, canonicalHistory, x_boards, y_boards, player_board, calls, False)

        if (s, a) in self.Qsa:
            assert (valids[a] != 0)
            self.Qsa[(s, a)] = (self.Nsa[(s, a)] * self.Qsa[(s, a)] + v) / (self.Nsa[(s, a)] + 1)
            self.Nsa[(s, a)] += 1
        else:
            self.Qsa[(s, a)] = v
            self.Nsa[(s, a)] = 1

        self.Ns[s] += 1

        return -v
    
    def predict(self, board):
        # randomly rotate and flip before network predict
        r = np.random.randint(8)
        nnet_input = board.get_canonical_history()
        nnet_input = board.rotate_history(r, nnet_input)
        pi, v = self.nnet.predict(nnet_input)

        # policy need to rotate and flip back
        pi_board = np.reshape(pi[:-1], (self.game.n, self.game.n))
        if r >= 4:
            pi_board = np.fliplr(pi_board)
        pi_board = np.rot90(pi_board, 4 - r % 4)
        p = list(pi_board.ravel()) + [pi[-1]]

        return p, v
    

    def checkScoreCache(self, board):
        non_canonical_s = self.game.stringRepresentation(board, is_canonical=False)
        if non_canonical_s not in self.Ss:
            return False, None
        else:
            return True, self.Ss[non_canonical_s]

    def clear(self):
        self.Qsa = {}  # stores Q values for s,a (as defined in the paper)
        self.Nsa = {}  # stores #times edge s,a was visited
        self.Ns = {}  # stores #times board s was visited
        self.Ps = {}  # stores initial policy (returned by neural net)
        self.Es = {}  # stores game.getGameEnded ended for board s
        self.Vs = {}  # stores game.getValidMoves for board s