from aimacode.planning import Action
from aimacode.search import Problem
from aimacode.utils import expr
from lp_utils import decode_state
from sys import maxsize

class PgNode():
    """Base class for planning graph nodes.

    includes instance sets common to both types of nodes used in a planning graph
    parents: the set of nodes in the previous level
    children: the set of nodes in the subsequent level
    mutex: the set of sibling nodes that are mutually exclusive with this node
    """

    def __init__(self):
        self.parents = set()
        self.children = set()
        self.mutex = set()

    def is_mutex(self, other) -> bool:
        """Boolean test for mutual exclusion

        :param other: PgNode
            the other node to compare with
        :return: bool
            True if this node and the other are marked mutually exclusive (mutex)
        """
        if other in self.mutex:
            return True
        return False

    def show(self):
        """helper print for debugging shows counts of parents, children, siblings

        :return:
            print only
        """
        print("{} parents".format(len(self.parents)))
        print("{} children".format(len(self.children)))
        print("{} mutex".format(len(self.mutex)))


class PgNode_s(PgNode):
    """A planning graph node representing a state (literal fluent) from a
    planning problem.

    Args:
    ----------
    symbol : str
        A string representing a literal expression from a planning problem
        domain.

    is_pos : bool
        Boolean flag indicating whether the literal expression is positive or
        negative.
    """

    def __init__(self, symbol: str, is_pos: bool):
        """S-level Planning Graph node constructor

        :param symbol: expr
        :param is_pos: bool
        Instance variables calculated:
            literal: expr
                    fluent in its literal form including negative operator if applicable
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous A level; initially empty
            children: set of nodes connected to this node in next A level; initially empty
            mutex: set of sibling S-nodes that this node has mutual exclusion with; initially empty
        """
        PgNode.__init__(self)
        self.symbol = symbol
        self.is_pos = is_pos
        self.literal = expr(self.symbol)
        if not self.is_pos:
            self.literal = expr('~{}'.format(self.symbol))

    def show(self):
        """helper print for debugging shows literal plus counts of parents,
        children, siblings

        :return:
            print only
        """
        if self.is_pos:
            print("\n*** {}".format(self.symbol))
        else:
            print("\n*** ~{}".format(self.symbol))
        PgNode.show(self)

    def __eq__(self, other):
        """equality test for nodes - compares only the literal for equality

        :param other: PgNode_s
        :return: bool
        """
        return (isinstance(other, self.__class__) and
                self.is_pos == other.is_pos and
                self.symbol == other.symbol)

    def __hash__(self):
        return hash(self.symbol) ^ hash(self.is_pos)


class PgNode_a(PgNode):
    """A-type (action) Planning Graph node - inherited from PgNode """


    def __init__(self, action: Action):
        """A-level Planning Graph node constructor

        :param action: Action
            a ground action, i.e. this action cannot contain any variables
        Instance variables calculated:
            An A-level will always have an S-level as its parent and an S-level as its child.
            The preconditions and effects will become the parents and children of the A-level node
            However, when this node is created, it is not yet connected to the graph
            prenodes: set of *possible* parent S-nodes
            effnodes: set of *possible* child S-nodes
            is_persistent: bool   True if this is a persistence action, i.e. a no-op action
        Instance variables inherited from PgNode:
            parents: set of nodes connected to this node in previous S level; initially empty
            children: set of nodes connected to this node in next S level; initially empty
            mutex: set of sibling A-nodes that this node has mutual exclusion with; initially empty
        """
        PgNode.__init__(self)
        self.action = action
        self.prenodes = self.precond_s_nodes()
        self.effnodes = self.effect_s_nodes()
        self.is_persistent = self.prenodes == self.effnodes
        self.__hash = None

    def show(self):
        """helper print for debugging shows action plus counts of parents, children, siblings

        :return:
            print only
        """
        print("\n*** {!s}".format(self.action))
        PgNode.show(self)

    def precond_s_nodes(self):
        """precondition literals as S-nodes (represents possible parents for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `prenodes` attribute.

        :return: set of PgNode_s
        """
        nodes = set()
        for p in self.action.precond_pos:
            nodes.add(PgNode_s(p, True))
        for p in self.action.precond_neg:
            nodes.add(PgNode_s(p, False))
        return nodes

    def effect_s_nodes(self):
        """effect literals as S-nodes (represents possible children for this node).
        It is computationally expensive to call this function; it is only called by the
        class constructor to populate the `effnodes` attribute.

        :return: set of PgNode_s
        """
        nodes = set()
        for e in self.action.effect_add:
            nodes.add(PgNode_s(e, True))
        for e in self.action.effect_rem:
            nodes.add(PgNode_s(e, False))
        return nodes

    def __eq__(self, other):
        """equality test for nodes - compares only the action name for equality

        :param other: PgNode_a
        :return: bool
        """
        return (isinstance(other, self.__class__) and
                self.is_persistent == other.is_persistent and
                self.action.name == other.action.name and
                self.action.args == other.action.args)

    def __hash__(self):
        self.__hash = self.__hash or hash(self.action.name) ^ hash(self.action.args)
        return self.__hash


def mutexify(node1: PgNode, node2: PgNode):
    """ adds sibling nodes to each other's mutual exclusion (mutex) set. These should be sibling nodes!

    :param node1: PgNode (or inherited PgNode_a, PgNode_s types)
    :param node2: PgNode (or inherited PgNode_a, PgNode_s types)
    :return:
        node mutex sets modified
    """
    if type(node1) != type(node2):
        raise TypeError('Attempted to mutex two nodes of different types')
    node1.mutex.add(node2)
    node2.mutex.add(node1)


class PlanningGraph():
    """
    A planning graph as described in chapter 10 of the AIMA text. The planning
    graph can be used to reason about 
    """

    def __init__(self, problem: Problem, state: str, serial_planning=True, short_curcuit=False):
        '''
        :param problem: PlanningProblem (or subclass such as AirCargoProblem or HaveCakeProblem)
        :param state: str (will be in form TFTTFF... representing fluent states)
        :param serial_planning: bool (whether or not to assume that only one action can occur at a time)
        Instance variable calculated:
            fs: FluentState
                the state represented as positive and negative fluent literal lists
            all_actions: list of the PlanningProblem valid ground actions combined with calculated no-op actions
            s_levels: list of sets of PgNode_s, where each set in the list represents an S-level in the planning graph
            a_levels: list of sets of PgNode_a, where each set in the list represents an A-level in the planning graph
        '''
        self.problem = problem
        self.fs = decode_state(state, problem.state_map)
        self.serial = serial_planning

        if not hasattr(problem, 'all_actions'):
            problem.all_actions = self.problem.actions_list + self.noop_actions(self.problem.state_map)
            problem.actions_for_preconds = self.precond_to_action(problem.all_actions)
            problem.goal_nodes = set()
            for exp in problem.goal:
                problem.goal_nodes.add(PgNode_s(exp, True))

        self.all_actions = problem.all_actions
        self.actions_for_preconds = problem.actions_for_preconds
        self.goal_nodes = problem.goal_nodes
        self.short_curcuit = short_curcuit

        self.s_levels = []  # type: List[List[PgNode_s]]
        self.a_levels = []  # type: List[List[PgNode_a]]
        self.create_graph()

    def precond_to_action(self, actions: Action):
        precond_map = {}

        # Initial both sets
        for expr in self.problem.state_map:
            precond_map[expr] = set()
            precond_map[~expr] = set()

        for action in actions:  # type: Action
            for precond in action.precond_pos:
                precond_map[precond].add(action)
            for precond in action.precond_neg:
                precond_map[~precond].add(action)

        return precond_map

    def noop_actions(self, literal_list):
        '''create persistent action for each possible fluent

        "No-Op" actions are virtual actions (i.e., actions that only exist in
        the planning graph, not in the planning problem domain) that operate
        on each fluent (literal expression) from the problem domain. No op
        actions "pass through" the literal expressions from one level of the
        planning graph to the next.

        The no-op action list requires both a positive and a negative action
        for each literal expression. Positive no-op actions require the literal
        as a positive precondition and add the literal expression as an effect
        in the output, and negative no-op actions require the literal as a
        negative precondition and remove the literal expression as an effect in
        the output.

        This function should only be called by the class constructor.

        :param literal_list:
        :return: list of Action
        '''

        action_list = []
        for fluent in literal_list:
            act1 = Action(expr("Noop_pos({})".format(fluent)), ([fluent], []), ([fluent], []))
            action_list.append(act1)
            act2 = Action(expr("Noop_neg({})".format(fluent)), ([], [fluent]), ([], [fluent]))
            action_list.append(act2)
        return action_list

    def create_graph(self, with_shortcut = False):
        """
        build a Planning Graph as described in Russell-Norvig 3rd Ed 10.3 or 2nd Ed 11.4

        The S0 initial level has been implemented for you.  It has no parents and includes all of
        the literal fluents that are part of the initial state passed to the constructor.  At the start
        of a problem planning search, this will be the same as the initial state of the problem.  However,
        the planning graph can be built from any state in the Planning Problem

        This function should only be called by the class constructor.

        :return:
            builds the graph by filling s_levels[] and a_levels[] lists with node sets for each level
        """

        # the graph should only be built during class construction
        if (len(self.s_levels) != 0) or (len(self.a_levels) != 0):
            raise Exception(
                'Planning Graph already created; construct a new planning graph for each new state in the planning sequence')

        # initialize S0 to literals in initial state provided.
        leveled = False
        level = 0
        self.s_levels.append(set())  # S0 set of s_nodes - empty to start
        # for each fluent in the initial state, add the correct literal PgNode_s
        for literal in self.fs.pos:
            self.s_levels[level].add(PgNode_s(literal, True))
        for literal in self.fs.neg:
            self.s_levels[level].add(PgNode_s(literal, False))
        # no mutexes at the first level

        # continue to build the graph alternating A, S levels until last two S levels contain the same literals,
        # i.e. until it is "leveled"
        while not leveled:
            self.add_action_level(level)
            if not self.short_curcuit:
                self.update_a_mutex(self.a_levels[level])

            level += 1
            self.add_literal_level(level)
            if not self.short_curcuit:
                self.update_s_mutex(self.s_levels[level])

            if self.s_levels[level] == self.s_levels[level - 1]:
                leveled = True

            # This is an problem-specific optimisation
            if self.short_curcuit and self.goal_nodes.issubset(self.s_levels[level]):
                return

        '''
        Note: For the intention of this assignment, I don't believe it's necessary to search until the graph is leveled.
        We can terminate as soon as as the goal state can be found/constructed at the last layer
        
        Add the following check for the speed up, inside above loop
        
            if self.goal_nodes.issubset(self.s_levels[level]):
                return
        '''

    def add_action_level(self, level):
        ''' add an A (action) level to the Planning Graph

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds A nodes to the current level in self.a_levels[level]
        '''

        # For the purpose of extracting the heuristic, we do not need to match the levels perfectly
        if self.short_curcuit:
            a_nodes = set()
            actions = set()
            for s_node in self.s_levels[level]:
                for action in self.actions_for_preconds[s_node.literal]:
                    actions.add(action)
            self.a_levels.append(map(lambda action: PgNode_a(action), actions))
            return

        # Standard implementation of add_action_level
        possible_actions = set()
        s_nodes = self.s_levels[level]  # type: set(PgNode_s)
        for s_node in s_nodes:  # type: PgNode_s
            for action in self.actions_for_preconds[s_node.literal]:
                possible_actions.add(action)

        a_nodes = set()
        for action in possible_actions:
            # We know that this action will be linked with at least an s_node, so let's create an a_node for it
            a_node = PgNode_a(action)
            # Find matching pairs of state-action
            # We didn't use set.intersection here because that method always prioritise/uses the smaller set's elements
            for matching_s_node in s_nodes:
                if matching_s_node in a_node.prenodes:
                    matching_s_node.children.add(a_node)
                    a_node.parents.add(matching_s_node)
                    a_nodes.add(a_node)

        self.a_levels.append(a_nodes)

    def add_literal_level(self, level):
        ''' add an S (literal) level to the Planning Graph

        :param level: int
            the level number alternates S0, A0, S1, A1, S2, .... etc the level number is also used as the
            index for the node set lists self.a_levels[] and self.s_levels[]
        :return:
            adds S nodes to the current level in self.s_levels[level]
        '''
        a_nodes = self.a_levels[level - 1]

        s_nodes = set()

        # Scan and generate all possible s_nodes
        for a_node in a_nodes:  # type: PgNode_a
            s_nodes = s_nodes.union(a_node.effnodes)

        # Linking them up
        for a_node in a_nodes:  # type: PgNode_a
            for matching_s_node in s_nodes.intersection(a_node.effnodes):  # type: PgNode_s
                a_node.children.add(matching_s_node)
                matching_s_node.parents.add(a_node)

        self.s_levels.append(s_nodes)

    def update_a_mutex(self, nodeset):
        """ Determine and update sibling mutual exclusion for A-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between two actions a given level
        if the planning graph is a serial planning graph and the pair are nonpersistence actions
        or if any of the three conditions hold between the pair:
           Inconsistent Effects
           Interference
           Competing needs

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        """
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if (self.serialize_actions(n1, n2) or
                        self.inconsistent_effects_mutex(n1, n2) or
                        self.interference_mutex(n1, n2) or
                        self.competing_needs_mutex(n1, n2)):
                    mutexify(n1, n2)

    def serialize_actions(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for mutual exclusion, returning True if the
        planning graph is serial, and if either action is persistent; otherwise
        return False.  Two serial actions are mutually exclusive if they are
        both non-persistent.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''
        #
        if not self.serial:
            return False
        if node_a1.is_persistent or node_a2.is_persistent:
            return False
        return True

    def inconsistent_effects_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for inconsistent effects, returning True if
        one action negates an effect of the other, and False otherwise.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''
        for x in node_a1.action.effect_add:
            if x in node_a2.action.effect_rem:
                return True

        for x in node_a2.action.effect_add:
            if x in node_a1.action.effect_rem:
                return True

        return False

    def interference_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for mutual exclusion, returning True if the
        effect of one action is the negation of a precondition of the other.

        HINT: The Action instance associated with an action node is accessible
        through the PgNode_a.action attribute. See the Action class
        documentation for details on accessing the effects and preconditions of
        an action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''

        return self.interfere_with(node_a2.action, node_a1.action) or self.interfere_with(node_a1.action,
                                                                                          node_a2.action)

    def interfere_with(self, a1: Action, a2: Action) -> bool:
        '''
        Read: a1 interfere with a2
        Test a pair of actions, return True if the effect of `a1` contradicts with the precondition of `a2`
        :param a1:
        :param a2:
        :return: bool
        '''
        for x in a1.effect_add:
            for y in a2.precond_neg:
                if x == y:
                    return True

        for x in a1.effect_rem:
            for y in a2.precond_pos:
                if x == y:
                    return True

        return False

    def competing_needs_mutex(self, node_a1: PgNode_a, node_a2: PgNode_a) -> bool:
        '''
        Test a pair of actions for mutual exclusion, returning True if one of
        the precondition of one action is mutex with a precondition of the
        other action.

        :param node_a1: PgNode_a
        :param node_a2: PgNode_a
        :return: bool
        '''

        for s1 in node_a1.parents:  # type: PgNode_s
            for s2 in node_a2.parents:  # type: PgNode_ss
                if s1.is_mutex(s2):
                    return True

        return False

    def update_s_mutex(self, nodeset: set):
        ''' Determine and update sibling mutual exclusion for S-level nodes

        Mutex action tests section from 3rd Ed. 10.3 or 2nd Ed. 11.4
        A mutex relation holds between literals at a given level
        if either of the two conditions hold between the pair:
           Negation
           Inconsistent support

        :param nodeset: set of PgNode_a (siblings in the same level)
        :return:
            mutex set in each PgNode_a in the set is appropriately updated
        '''
        nodelist = list(nodeset)
        for i, n1 in enumerate(nodelist[:-1]):
            for n2 in nodelist[i + 1:]:
                if self.negation_mutex(n1, n2) or self.inconsistent_support_mutex(n1, n2):
                    mutexify(n1, n2)

    def negation_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s) -> bool:
        '''
        Test a pair of state literals for mutual exclusion, returning True if
        one node is the negation of the other, and False otherwise.

        HINT: Look at the PgNode_s.__eq__ defines the notion of equivalence for
        literal expression nodes, and the class tracks whether the literal is
        positive or negative.

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        '''
        return node_s1.symbol == node_s2.symbol and node_s1.is_pos != node_s2.is_pos

    def inconsistent_support_mutex(self, node_s1: PgNode_s, node_s2: PgNode_s):
        '''
        Test a pair of state literals for mutual exclusion, returning True if
        there are no actions that could achieve the two literals at the same
        time, and False otherwise.  In other words, the two literal nodes are
        mutex if all of the actions that could achieve the first literal node
        are pairwise mutually exclusive with all of the actions that could
        achieve the second literal node.

        HINT: The PgNode.is_mutex method can be used to test whether two nodes
        are mutually exclusive.

        :param node_s1: PgNode_s
        :param node_s2: PgNode_s
        :return: bool
        '''

        for a_node_1 in node_s1.parents:  # type: PgNode_a
            for a_node_2 in node_s2.parents:  # type: PgNode_a
                if not a_node_1.is_mutex(a_node_2):
                    return False

        return True

    def h_levelsum(self) -> int:
        '''The sum of the level costs of the individual goals (admissible if goals independent)

        :return: int
        '''
        level_sum = 0
        # for each goal in the problem, determine the level cost, then add them together

        goal_count = 0
        total_goal_count = len(self.problem.goal)

        goal_states = set()
        for goal_expr in self.problem.goal:  # type: expr
            goal_states.add(PgNode_s(goal_expr, True))

        for i, s_nodes in enumerate(self.s_levels):
            found_goals = set()
            for x in s_nodes.intersection(goal_states):
                found_goals.add(x)
                goal_states.remove(x)
                level_sum += i
                goal_count += 1

            # We achieved all goals
            if goal_count == total_goal_count:
                break

        return level_sum if goal_count == total_goal_count else maxsize
