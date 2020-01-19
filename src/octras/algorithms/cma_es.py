import numpy as np
import numpy.linalg as la

import logging
logger = logging.getLogger(__name__)

# https://en.wikipedia.org/wiki/CMA-ES
def cma_es_algorithm(calibrator, candidate_set_size = None, initial_step_size = 0.3):
    # Initialize state
    initial_parameters = [p["initial"] for p in calibrator.problem.parameters]
    N = len(initial_parameters)

    mean = np.copy(initial_parameters).reshape((N,1))
    sigma = initial_step_size

    # Selection parameters
    L_default = 4 + int(np.floor(3 * np.log(N)))
    L = L_default if candidate_set_size is None else candidate_set_size

    if not candidate_set_size is None and candidate_set_size < L_default:
        logger.warning("Using requested candidate set size %d (recommended is at least %d!)" % (candidate_set_size, L_default))

    mu = L / 2.0
    weights = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
    mu = int(np.floor(mu))
    weights = weights[:mu] / np.sum(weights[:mu])
    mueff = np.sum(weights)**2 / np.sum(weights ** 2)

    # Adaptation parameters
    cc = (4 + mueff / N) / (N + 4 + 2.0 * mueff / N)
    cs = (mueff + 2.0) / (N + mueff + 5.0)
    c1 = 2.0 / ((N + 1.3)**2 + mueff)
    cmu = min(1.0 - c1, 2.0 * (mueff - 2.0 + 1.0 / mueff) / ((N + 2.0)**2 + mueff))
    damps = 1.0 + 2.0 * max(0, np.sqrt((mueff - 1.0) / (N + 1.0)) - 1.0) + cs

    # Initialize dynamic parameters
    pc = np.zeros((N,1))
    ps = np.zeros((N,1))
    B = np.eye(N)
    D = np.ones((N,))
    C = np.dot(B, np.dot(np.diag(D**2), B.T))
    invsqrtC = np.dot(B, np.dot(np.diag(D**-1), B.T))
    eigeneval = 0
    counteval = 0
    chiN = N**0.5 * (1.0 - 1.0 / (4.0 * N) + 1.0 / (21.0 * N**2))

    # Start algorithm
    cma_es_iteration = 0

    while not calibrator.finished:
        cma_es_iteration += 1
        logger.info("Starting CMA-ES iteration %d." % cma_es_iteration)

        annotations = {
            "mean": mean,
            "covariance": C, "pc": pc, "ps": ps,
            "sigma": sigma
        }

        # Generate new samples
        counteval += L

        candidate_parameters = sigma * np.dot((np.random.normal(size = (N, L)) * D[:, np.newaxis]).T, B) + mean.T

        candidate_identifiers = [
            calibrator.schedule(parameters, annotations = annotations)
            for parameters in candidate_parameters
        ]

        # Wait for samples
        calibrator.wait()

        # Obtain fitness
        candidate_objectives = np.array([
            calibrator.get(identifier)[0] # We minimize!
            for identifier in candidate_identifiers
        ])

        # Cleanup
        for identifier in candidate_identifiers:
            calibrator.cleanup(identifier)

        sorter = np.argsort(candidate_objectives)

        candidate_objectives = candidate_objectives[sorter]
        candidate_parameters = candidate_parameters[sorter, :]

        # Update mean
        previous_mean = mean
        mean = np.sum(candidate_parameters[:mu] * weights[:, np.newaxis], axis = 0).reshape((N, 1))

        # Update evolution paths

        psa = (1.0 - cs ) * ps
        psb = np.sqrt(cs * (2.0 - cs) * mueff) * np.dot(invsqrtC, mean - previous_mean) / sigma
        ps = psa + psb

        hsig = la.norm(ps) / np.sqrt(1.0 - (1.0 - cs)**(2.0 * counteval / L)) / chiN < 1.4 + 2.0 / (N + 1.0)
        pca = (1.0 - cc) * pc
        pcb = hsig * np.sqrt(cc * (2.0 - cc) * mueff) * (mean - previous_mean) / sigma
        pc = pca + pcb

        # Adapt covariance matrix
        artmp = (1.0 / sigma) * (candidate_parameters[:mu].T - previous_mean)


        Ca = (1.0 - c1 - cmu) * C
        Cb = c1 * (np.dot(pc, pc.T) + (not hsig) * cc * (2.0 - cc) * C)
        Cc = cmu * np.dot(artmp, np.dot(np.diag(weights), artmp.T))
        C = Ca + Cb + Cc

        # Adapt step size
        sigma = sigma * np.exp((cs / damps) * (la.norm(ps) / chiN - 1.0))

        if counteval - eigeneval > L / (c1 + cmu) / N / 10.0:
            eigeneval = counteval
            C = np.triu(C) + np.triu(C, 1).T
            d, B = la.eig(C)

            D = np.sqrt(d)
            Dm = np.diag(1.0 / np.sqrt(d))

            invsqrtC = np.dot(B.T, np.dot(Dm, B))

        if np.max(D) > 1e7 * np.min(D):
            logger.warning("Condition exceeds 1e14")