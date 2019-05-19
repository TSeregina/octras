import uuid, time
import numpy as np
import scipy.optimize

from octras.tests.utils import QuadraticSumSimulator, RealDimensionalProblem
from octras.simulation import Scheduler
from octras.optimization import Optimizer

from octras.algorithms.random_walk import random_walk_algorithm
from octras.algorithms.scipy import scipy_algorithm
from octras.algorithms.spsa import spsa_algorithm
from octras.algorithms.fdsa import fdsa_algorithm

def test_random_walk():
    np.random.seed(0)

    simulator = QuadraticSumSimulator([2.0, 4.0])
    problem = RealDimensionalProblem(2)

    scheduler = Scheduler(simulator, ping_time = 0.0)
    optimizer = Optimizer(scheduler, problem, maximum_evaluations = 100, log_path = "/home/sebastian/rw.p")

    random_walk_algorithm(optimizer, [(-5.0, 5.0)] * 2)
    assert optimizer.best_objective < 1.0
