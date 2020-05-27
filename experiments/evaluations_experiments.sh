# "per_pos_item_idx",
# "per_item",
# "per_item_in_first_pos",
# "per_item_given_pos",
# "per_logistic_regression_of_pos_item_idx_and_item",
# "per_logistic_regression_of_pos_item_idx_and_item_ps",


PYTHONPATH="." luigi --module recommendation.task.model.trivago.evaluation EvaluateTrivagoTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____epsilon_greedy_6a1d38dd73 --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining --fill-ps-strategy per_logistic_regression_of_pos_item_idx_and_item_ps


PYTHONPATH="." luigi --module recommendation.task.model.evaluation EvaluateTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____softmax_explorer_ecf6ca42ee --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining

PYTHONPATH="." luigi --module recommendation.task.model.trivago.evaluation EvaluateTrivagoTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____softmax_explorer_ecf6ca42ee --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining --fill-ps-strategy per_pos_item_idx

PYTHONPATH="." luigi --module recommendation.task.model.trivago.evaluation EvaluateTrivagoTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____softmax_explorer_ecf6ca42ee --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining --fill-ps-strategy per_item

PYTHONPATH="." luigi --module recommendation.task.model.trivago.evaluation EvaluateTrivagoTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____softmax_explorer_ecf6ca42ee --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining --fill-ps-strategy per_item_in_first_pos

PYTHONPATH="." luigi --module recommendation.task.model.trivago.evaluation EvaluateTrivagoTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____softmax_explorer_ecf6ca42ee --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining --fill-ps-strategy per_item_given_pos

PYTHONPATH="." luigi --module recommendation.task.model.trivago.evaluation EvaluateTrivagoTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____softmax_explorer_ecf6ca42ee --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining --fill-ps-strategy per_logistic_regression_of_pos_item_idx_and_item

PYTHONPATH="." luigi --module recommendation.task.model.trivago.evaluation EvaluateTrivagoTestSetPredictions --model-module recommendation.task.model.trivago.trivago_logistic_model --model-cls TrivagoLogisticModelInteraction --model-task-id TrivagoLogisticModelInteraction_selu____softmax_explorer_ecf6ca42ee --fairness-columns "[\"device_idx\", \"platform_idx\"]" --local-scheduler --direct-estimator-module recommendation.task.model.trivago.trivago_logistic_model --direct-estimator-cls TrivagoLogisticModelTraining --fill-ps-strategy per_logistic_regression_of_pos_item_idx_and_item_ps --direct-estimator-negative-proportion 0.02
