PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote --bandit-policy-params '{"endpoints": ["http://localhost:5000/rank"]}' --obs-batch-size 1 --val-size 0 --obs "RandomRankingRecommender"

PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote --bandit-policy-params '{"endpoints": ["http://localhost:5001/rank"]}' --obs-batch-size 1 --val-size 0 --obs "MostPopularRankingRecommender"

PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote --bandit-policy-params '{"endpoints": ["http://localhost:5002/rank"]}' --obs-batch-size 1 --val-size 0 --obs "MostPopularPerUserRankingRecommender"

PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote --bandit-policy-params '{"endpoints": ["http://localhost:5003/rank"]}' --obs-batch-size 1 --val-size 0 --obs "MatrixFactorizationRankingRecommender"

PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote --bandit-policy-params '{"endpoints": ["http://localhost:5004/rank"]}' --obs-batch-size 1 --val-size 0 --obs "AutoEncoderRankingRecommender"


PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote_epsilon_greedy --bandit-policy-params '{"endpoints": ["http://localhost:5000/rank", "http://localhost:5001/rank", "http://localhost:5002/rank", "http://localhost:5003/rank", "http://localhost:5004/rank"]}' --obs-batch-size 1 --val-size 0 --obs "Embedding"

PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote_ucb --bandit-policy-params '{"endpoints": ["http://localhost:5000/rank", "http://localhost:5001/rank", "http://localhost:5002/rank", "http://localhost:5003/rank", "http://localhost:5004/rank"]}' --obs-batch-size 1 --val-size 0 --obs "Embedding"

PYTHONPATH="." luigi --module recommendation.task.model.ensamble_mab EnsambleMABInteraction --project ifood_ensamble_mab --bandit-policy remote_softmax --bandit-policy-params '{"endpoints": ["http://localhost:5000/rank", "http://localhost:5001/rank", "http://localhost:5002/rank", "http://localhost:5003/rank", "http://localhost:5004/rank"]}' --obs-batch-size 1 --val-size 0 --obs "Embedding"


PYTHONPATH="." luigi --module recommendation.task.data_preparation.new_ifood IndexDataset