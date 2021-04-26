from octras import Evaluator, Loop
from octras.matsim import MATSimSimulator
from octras.tracker import PickleTracker

from octras.algorithms import RandomWalk, CMAES, SPSA, NelderMead #, BatchBayesianOptimization

from problem import ParisProblem
from analyzer import ParisAnalyzer

import logging
logging.basicConfig(level = logging.INFO)

threads_per_simulation = 4
parallel_simulations = 1
iterations = 60

output_path = "optimization.p"

reference_path = "resources/reference_trips.csv"
config_path = "resources/scenario/ile_de_france_config.xml"

simulator = MATSimSimulator(
    working_directory = "work",
    class_path = "resources/ile_de_france-1.2.1.jar",
    main_class = "org.eqasim.ile_de_france.RunSimulation"
)

analyzer = ParisAnalyzer(
    threshold = 0.05,
    number_of_bounds = 40,
    minimum_distance = 100.0,
    maximum_distance = 40.0 * 1e3, # dict(region = 40 * 1e3, paris = 20 * 1e3),
    reference_path = reference_path
)

problem = ParisProblem(analyzer,
    threads = threads_per_simulation,
    iterations = iterations,
    config_path = config_path
)

evaluator = Evaluator(
    problem = problem,
    simulator = simulator,
    parallel = parallel_simulations
)

algorithm = SPSA(
    evaluator = evaluator,
    perturbation_factor = 0.1,
    gradient_factor = 0.5,
    perturbation_exponent = 0.101,
    gradient_exponent = 0.602,
    gradient_offset = 0
)

tracker = PickleTracker(output_path)

Loop().run(
    evaluator = evaluator,
    algorithm = algorithm, tracker = tracker
)
