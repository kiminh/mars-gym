import os
import re
from collections import Counter
from pyspark.sql.functions import posexplode, explode#, arrays_zip
import re
from scipy.sparse.csr import csr_matrix

import luigi
import math
import numpy as np
import pandas as pd
from pyspark import SparkContext
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.functions import collect_set, collect_list, lit, sum, udf, concat_ws, col, count, abs, date_format, max, \
    from_utc_timestamp, expr
from pyspark.sql.functions import explode, posexplode
from pyspark.sql.types import IntegerType, StringType
from pyspark.sql.window import Window
from torchnlp.encoders import LabelEncoder
from torchnlp.encoders.text.static_tokenizer_encoder import StaticTokenizerEncoder
from unidecode import unidecode
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from pyspark.sql.types import ArrayType, FloatType

from recommendation.task.data_preparation.base import BasePySparkTask, BasePrepareDataFrames
from recommendation.utils import parallel_literal_eval, datetime_to_shift, date_to_day_of_week, date_to_day_of_month, clean_filename, literal_eval_if_str
from pyspark.sql.window import Window
import pyspark.sql.functions as func
from pyspark.sql.functions import when
from sklearn.preprocessing import MinMaxScaler
from pyspark.ml.feature import QuantileDiscretizer

BASE_DIR: str = os.path.join("output", "trivago")
DATASET_DIR: str = os.path.join("output", "trivago", "dataset")
FILES_DIR: str = os.path.join("files")


def to_array(xs):
    return [literal_eval_if_str(c) if isinstance(literal_eval_if_str(c), int) or isinstance(literal_eval_if_str(c), float) else literal_eval_if_str(c)[0] 
                for c in literal_eval_if_str(xs)] if xs is not None else None
to_array_int_udf   = udf(lambda x: to_array(x), ArrayType(IntegerType()))
to_array_float_udf = udf(lambda x: to_array(x), ArrayType(FloatType()))
array_mean         = udf(lambda x: float(np.mean(x)), FloatType())

class CheckDataset(luigi.Task):
    def output(self):
        return luigi.LocalTarget(os.path.join(BASE_DIR, "trivagoRecSysChallengeData2019_v2", "train.csv")), \
               luigi.LocalTarget(os.path.join(BASE_DIR, "trivagoRecSysChallengeData2019_v2", "item_metadata.csv"))

    def run(self):
        raise AssertionError(
            f"As seguintes pastas são esperadas com o dataset: {[output.path for output in self.output()]}")

class FilterDataset(BasePySparkTask):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')

    def requires(self):
      return CheckDataset()

    def output(self):
      return luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "train__size=%d.csv" % (self.sample_size))),\
              luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "item_metadata__size=%d.csv" % (self.sample_size)))

    def main(self, sc: SparkContext, *args):
      os.makedirs(os.path.join(DATASET_DIR, clean_filename(self.filter_city)), exist_ok=True)

      spark    = SparkSession(sc)
      train_df = spark.read.csv(self.input()[0].path, header=True, inferSchema=True)
      train_df = train_df.withColumn("impressions_array", F.split(train_df.impressions, "\|"))

      meta_df  = spark.read.csv(self.input()[1].path, header=True, inferSchema=True)

      # Filter dataset
      if self.filter_city != 'all':
        train_df     = train_df.filter(train_df.city==self.filter_city)
        
        # Filter reference
        reference_df = train_df.select("reference").distinct()
        
        # Filte item impressions
        item_id_df   = train_df.select(posexplode("impressions_array").alias("pos_item_idx", "reference")).select("reference").distinct()
        #raise(Exception(train_df.show()))
        item_id_df   = item_id_df.union(reference_df).select("reference").distinct()

        meta_df      = meta_df.join(item_id_df, meta_df.item_id == item_id_df.reference).select("item_id","properties")
      if self.sample_size > 0:
        train_df = train_df.sort("timestamp", ascending=False).limit(self.sample_size)

      # Save
      train_df.toPandas().to_csv(self.output()[0].path, index=False)
      meta_df.toPandas().to_csv(self.output()[1].path, index=False)

class TransformMetaDataset(luigi.Task):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')

    def requires(self):
      return FilterDataset(sample_size=self.sample_size, filter_city=self.filter_city)

    def output(self):
      return luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "item_metadata_transform__size=%d.csv" % (self.sample_size)))

    # 'a|b|c' -> ['a', 'b', 'c']
    #
    # 
    def split_df_columns(self, df, column):
      tf = CountVectorizer(tokenizer=lambda x: x.split("|"))
      tf_df = tf.fit_transform(df[column]).todense()
      tf_df = pd.DataFrame(tf_df, columns = sorted(tf.vocabulary_.keys()))
      return tf_df
      
    def run(self):
      df_meta = pd.read_csv(self.input()[1].path)  

      tf_prop_meta = self.split_df_columns(df_meta, 'properties')
      df_meta      = df_meta.join(tf_prop_meta).drop(['properties'], axis=1)#.shift(periods=1, fill_value=0)
      df_meta      = df_meta.append({'item_id': 0}, ignore_index=True).fillna(0) # Unknown
      df_meta      = df_meta.astype(int)
      
      df_meta['star'] = df_meta['1 star']*1 + df_meta['2 star']*2 + df_meta['3 star']*3 + df_meta['4 star']*4 + df_meta['5 star']*5
      df_meta['list_metadata'] = df_meta.drop('item_id', 1).values.tolist()

      df_meta.sort_values('item_id').to_csv(self.output().path, index=False)

class TransformSessionDataset(luigi.Task):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')

    def requires(self):
      return FilterDataset(sample_size=self.sample_size, filter_city=self.filter_city)

    def output(self):
      return luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "train_transform__size=%d.csv" % (self.sample_size))),\
              luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "text_vocabulary__size=%d.csv" % (self.sample_size))),\
              luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "filter_session_size=%d.csv" % (self.sample_size)))


    # 'a|b|c' -> ['a', 'b', 'c']
    #
    # 
    def split_df_columns(self, df, column):
      tf = CountVectorizer(tokenizer=lambda x: x.split("|"))
      tf_df = tf.fit_transform(df[column].fillna("")).todense()
      tf_df = pd.DataFrame(tf_df, columns = sorted(tf.vocabulary_.keys()))
      tf_df.columns = [column+"_"+c.replace(" ", "_") for c in tf_df.columns]
      return tf_df

    def run(self):
      df        = pd.read_csv(self.input()[0].path)  

      # Transform impressions, prices
      df['impressions'] = df['impressions'].fillna("").apply(lambda x: [] if x == "" else [int(i) for i in x.split("|")] )
      df['prices']      = df['prices'].fillna("").apply(lambda x: [] if x == "" else [float(p) for p in x.split("|")])

      # Transform current_filters

      df_current_filters = self.split_df_columns(df, 'current_filters')
      #df      = df.join(tf_current_filters).drop(['properties'], axis=1)#.shift(periods=1, fill_value=0)
      df['list_current_filters'] = df_current_filters.values.tolist()
      df  = df.join(df_current_filters).drop(['current_filters'], axis=1)#.shift(periods=1, fill_value=0)

      # Transform reference in action_type

      for ref in ["interaction item image", "search for poi", "interaction item rating", "clickout item", 
                  "interaction item deals", "change of sort order", "search for item", "search for destination", 
                    "filter selection", "interaction item info"]:
        # clickout item: user makes a click-out on the item and gets forwarded to a partner website. The reference value for this action is the item_id. Other items that were displayed to the user and their associated prices are listed under the ‘impressions’ and ‘prices’ column for this action.
        # interaction item rating: user interacts with a rating or review of an item.
        #   The reference value for this action is the item id.
        # interaction item info: user interacts with item information.
        #   The reference value for this action is the item id.
        # interaction item image: user interacts with an image of an item.
        #   The reference value for this action is the item id.
        # interaction item deals: user clicks on the view more deals button.
        #   The reference value for this action is the item id.
        # change of sort order: user changes the sort order.
        #   The reference value for this action is the sort order description.
        # filter selection: user selects a filter.
        #   The reference value for this action is the filter description.
        # search for item: user searches for an accommodation.
        #   The reference value for this action is the item id.
        # search for destination: user searches for a destination.
        #   The reference value for this action is the name of the destination.
        # search for poi: user searches for a point of interest (POI).
        #   The reference value for this action is the name of the POI.     
        df['reference_'+clean_filename(ref)] = df.apply(lambda row: row['reference'] if row['action_type'] == ref else "<none>", axis=1)


      # Transform columns with text
      columns_with_string = ["reference_search_for_poi","reference_change_of_sort_order",
                            "reference_search_for_destination","reference_filter_selection"]
      # vocabulario
      vocab = ["<none>"]
      for c in columns_with_string:
        vocab  += df[c].fillna("<none>").tolist()

      # Tokenizer
      tokenizer = StaticTokenizerEncoder(vocab, tokenize=lambda x: re.split('\W+', x), min_occurrences=1, reserved_tokens=[])

      #Apply tokenizer
      for text_column in columns_with_string:
        df[text_column] = tokenizer.batch_encode(df[text_column].fillna("<none>"))[0].cpu().detach().numpy().tolist()
        df[text_column + '_max_words'] = len(df[text_column][0])

      # Save
      df.to_csv(self.output()[0].path, index=False)
      pd.DataFrame(tokenizer.vocab, columns=['vocabulary']).to_csv(self.output()[1].path)
      df_current_filters.to_csv(self.output()[2].path)
      
class GenerateIndicesDataset(BasePySparkTask):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')

    def requires(self):
      return FilterDataset(sample_size=self.sample_size, filter_city=self.filter_city),\
        TransformMetaDataset(sample_size=self.sample_size, filter_city=self.filter_city)

    def output(self):
      return luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "item_indices__size=%d.csv" % (self.sample_size))),\
            luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city),  "user_indices__size=%d.csv" % (self.sample_size))),\
            luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city),  "session_indices__size=%d.csv" % (self.sample_size))),\
            luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city),  "action_type_indices__size=%d.csv" % (self.sample_size))),\
            luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city),  "platform_indices__size=%d.csv" % (self.sample_size))),\
            luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city),  "city_indices__size=%d__csv" % (self.sample_size))),\
            luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city),  "device_indices__size=%d.csv" % (self.sample_size))),\

    def main(self, sc: SparkContext, *args):
      os.makedirs(DATASET_DIR, exist_ok=True)

      spark = SparkSession(sc)

      # Load
      train_df = spark.read.csv(self.input()[0][0].path, header=True, inferSchema=True)
      meta_df  = spark.read.csv(self.input()[1].path, header=True, inferSchema=True)

      # Extract
      item_idx_df    = meta_df.select("item_id").distinct().orderBy("item_id").toPandas()
      user_idx_df    = train_df.select("user_id").distinct().toPandas()
      session_idx_df = train_df.select("session_id").distinct().toPandas()
      action_type_idx_df = train_df.select("action_type").distinct().toPandas()\
                            .append({'action_type': '<none>'}, ignore_index=True).sort_values("action_type").reset_index(drop=True)
      platform_idx_df = train_df.select("platform").distinct().toPandas()
      city_idx_df     = train_df.select("city").distinct().toPandas()
      device_idx_df   = train_df.select("device").distinct().toPandas()

      # Save
      item_idx_df.to_csv(self.output()[0].path, index_label="item_idx")
      user_idx_df.to_csv(self.output()[1].path, index_label="user_idx")
      session_idx_df.to_csv(self.output()[2].path, index_label="session_idx")
      action_type_idx_df.to_csv(self.output()[3].path, index_label="action_type_idx")
      platform_idx_df.to_csv(self.output()[4].path, index_label="platform_idx")
      city_idx_df.to_csv(self.output()[5].path, index_label="city_idx")
      device_idx_df.to_csv(self.output()[6].path, index_label="device_idx")

class CreateIndexDataset(BasePySparkTask):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')

    def requires(self):
      return  TransformSessionDataset(sample_size=self.sample_size, filter_city=self.filter_city),\
              TransformMetaDataset(sample_size=self.sample_size, filter_city=self.filter_city),\
              GenerateIndicesDataset(sample_size=self.sample_size, filter_city=self.filter_city)

    def output(self):
      return luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "train_indexed__size=%d.csv" % (self.sample_size))),\
              luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "item_metadata_indexed__size=%d.csv" % (self.sample_size)))


    def main(self, sc: SparkContext, *args):
      os.makedirs(DATASET_DIR, exist_ok=True)
      spark = SparkSession(sc)

      train_df           = spark.read.csv(self.input()[0][0].path, header=True, inferSchema=True)
      meta_df            = spark.read.csv(self.input()[1].path, header=True, inferSchema=True)

      item_idx_df        = spark.read.csv(self.input()[2][0].path, header=True, inferSchema=True)
      user_idx_df        = spark.read.csv(self.input()[2][1].path, header=True, inferSchema=True)
      session_idx_df     = spark.read.csv(self.input()[2][2].path, header=True, inferSchema=True)
      action_type_idx_df = spark.read.csv(self.input()[2][3].path, header=True, inferSchema=True)
      platform_idx_df    = spark.read.csv(self.input()[2][4].path, header=True, inferSchema=True)
      city_idx_df        = spark.read.csv(self.input()[2][5].path, header=True, inferSchema=True)
      device_idx_df      = spark.read.csv(self.input()[2][6].path, header=True, inferSchema=True)

      
      # Join with item_idx 
      for c in ["reference_interaction_item_image","reference_interaction_item_rating","reference_clickout_item",
                "reference_interaction_item_deals","reference_search_for_item","reference_interaction_item_info"]:
        train_df = train_df.\
                   join(item_idx_df.withColumnRenamed("item_id",c).withColumnRenamed("item_idx",c+"_idx"), c,how='left').\
                   fillna(0)

      # Joint others index
      train_df = train_df.\
        join(user_idx_df, "user_id").\
        join(session_idx_df, "session_id").\
        join(action_type_idx_df, "action_type").\
        join(platform_idx_df, "platform").\
        join(city_idx_df, "city").\
        join(device_idx_df, "device")

      # Index impressions
      #item_idx_df = item_idx_df.set_index('item_id')

      # Joint meta
      meta_df = meta_df.join(item_idx_df, "item_id")
      current_filtes_name = [c for c in train_df.schema.names if "current_filters_" in c and c!="current_filters_"] #current_filters.air conditioning
      
      # Save
      columns = ["timestamp","step", "user_idx", "session_idx", "action_type", "action_type_idx", 
                  "reference_search_for_poi","reference_change_of_sort_order",
                  "reference_search_for_destination","reference_filter_selection",
                  "reference_interaction_item_image_idx","reference_interaction_item_rating_idx","reference_clickout_item_idx",
                  "reference_interaction_item_deals_idx","reference_search_for_item_idx","reference_interaction_item_info_idx",
                  "platform_idx", "city_idx", "device_idx", "list_current_filters", "impressions", "prices"]
      columns.extend(current_filtes_name)     
      df = train_df.select(columns).toPandas()
      
      df.to_csv(self.output()[0].path, index=False)
      meta_df.toPandas().to_csv(self.output()[1].path, index=False)

class CreateAggregateIndexDataset(BasePySparkTask):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')
    window_hist: int = luigi.IntParameter(default=5)

    def requires(self):
      return  CreateIndexDataset(sample_size=self.sample_size, filter_city=self.filter_city)

    def output(self):
      return luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "train__agg_indexed__size=%d_window=%d.csv" % (self.sample_size, self.window_hist)))

    def main(self, sc: SparkContext, *args):
      os.makedirs(DATASET_DIR, exist_ok=True)
      spark = SparkSession(sc)

      # ['timestamp', 'step', 'user_idx', 'session_idx', 'action_type_idx',
      #  'reference_search_for_poi', 'reference_change_of_sort_order',
      #  'reference_search_for_destination', 'reference_filter_selection',
      #  'reference_interaction_item_image_idx',
      #  'reference_interaction_item_rating_idx', 'reference_clickout_item_idx',
      #  'reference_interaction_item_deals_idx', 'reference_search_for_item_idx',
      #  'reference_interaction_item_info_idx', 'platform_idx', 'city_idx',
      #  'device_idx', 'current_filters', 'impressions', 'prices'],
      train_df = spark.read.csv(self.input()[0].path, header=True, inferSchema=True)

      win_over_session = Window.partitionBy('session_idx').orderBy('timestamp')\
                          .rangeBetween(Window.unboundedPreceding, -1)
      win_over_session_with_current = Window.partitionBy('session_idx').orderBy('timestamp')\
                          .rangeBetween(Window.unboundedPreceding, 0)

      def _pad_sequence(seq, pad) -> np.ndarray:
        if seq is None:
          return None
        else:
          return (([0] * pad) + seq)[-pad:]

      def to_array(xs):
          return [literal_eval_if_str(c) if isinstance(literal_eval_if_str(c), int) else literal_eval_if_str(c)[0] for c in literal_eval_if_str(xs)] if xs is not None else None
      to_array_udf = udf(lambda x: _pad_sequence(to_array(x), self.window_hist), ArrayType(IntegerType()))


      df_group = train_df.\
                  withColumn("timestamp_diff", F.sum(col("timestamp")).over(win_over_session_with_current)-col("timestamp")).\
                  withColumn("step",                                  (max("step").over(win_over_session)+lit(1)).cast(IntegerType())).\
                  withColumn("list_reference_search_for_poi",         to_array_udf(collect_list("reference_search_for_poi").over(win_over_session))).\
                  withColumn("list_reference_change_of_sort_order",   to_array_udf(collect_list("reference_change_of_sort_order").over(win_over_session))).\
                  withColumn("list_reference_search_for_destination", to_array_udf(collect_list("reference_search_for_destination").over(win_over_session))).\
                  withColumn("list_reference_filter_selection",       to_array_udf(collect_list("reference_filter_selection").over(win_over_session))).\
                  withColumn("list_reference_interaction_item_image_idx",   to_array_udf(collect_list("reference_interaction_item_image_idx").over(win_over_session))).\
                  withColumn("list_reference_interaction_item_rating_idx",  to_array_udf(collect_list("reference_interaction_item_rating_idx").over(win_over_session))).\
                  withColumn("list_reference_clickout_item_idx",      to_array_udf(collect_list("reference_clickout_item_idx").over(win_over_session))).\
                  withColumn("list_reference_interaction_item_deals_idx",   to_array_udf(collect_list("reference_interaction_item_deals_idx").over(win_over_session))).\
                  withColumn("list_reference_search_for_item_idx",    to_array_udf(collect_list("reference_search_for_item_idx").over(win_over_session))).\
                  withColumn("list_reference_interaction_item_info_idx",    to_array_udf(collect_list("reference_interaction_item_info_idx").over(win_over_session))).\
                  withColumn("list_action_type_idx",                  to_array_udf(collect_list("action_type_idx").over(win_over_session))).\
                  withColumn("action_type_item_idx",  
                                          when(train_df.action_type == "interaction item image", col("reference_interaction_item_image_idx")).\
                                          when(train_df.action_type == "interaction item rating", col("reference_interaction_item_rating_idx")).\
                                          when(train_df.action_type == "clickout item", col("reference_clickout_item_idx")).\
                                          when(train_df.action_type == "interaction item deals", col("reference_interaction_item_deals_idx")).\
                                          when(train_df.action_type == "search for item", col("reference_search_for_item_idx")).\
                                          when(train_df.action_type == "interaction item info", col("reference_interaction_item_info_idx")).\
                                          otherwise(0)).\
                  withColumn("clicked",   when(train_df.action_type == "clickout item", 1.0).otherwise(0.0)).\
                  orderBy("timestamp")

      # add feature 'sum_action_before'
      win_item_action  = Window.partitionBy('session_idx', 'action_type_item_idx').orderBy('timestamp') \
                          .rangeBetween(Window.unboundedPreceding, -1)

      df_group         = df_group.withColumn("view", lit(1.0))\
                                 .withColumn("sum_action_item_before", F.sum(col("view")).over(win_item_action))\
                                 .fillna(0, subset=["sum_action_item_before"])


      # Filter only action type - clickout item
      df_group = df_group.filter(df_group.action_type == "clickout item") # 3,clickout item

      columns  = ['timestamp', 'timestamp_diff', 'step', 'user_idx', 'session_idx', 'city_idx', 'sum_action_item_before', 'action_type_item_idx', 'action_type_idx',
                  'list_action_type_idx', 'list_reference_search_for_poi', 'list_reference_change_of_sort_order',
                  'list_reference_search_for_destination', 'list_reference_filter_selection', 'list_reference_interaction_item_image_idx',
                  'list_reference_interaction_item_rating_idx', 'list_reference_clickout_item_idx', 'list_reference_interaction_item_deals_idx',
                  'list_reference_search_for_item_idx', 'list_reference_interaction_item_info_idx', 
                  'list_current_filters', 'platform_idx', 'device_idx', 'impressions', 'prices', 'clicked']
                  
      columns.extend([c for c in df_group.schema.names if "current_filters_" in c and c!="current_filters_"])     

      df_group.select(columns).toPandas().to_csv(self.output().path, index=False)

class CreateExplodeWithNoClickIndexDataset(BasePySparkTask):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')
    window_hist: int = luigi.IntParameter(default=5)

    def requires(self):
      return  CreateAggregateIndexDataset(sample_size=self.sample_size, filter_city=self.filter_city, window_hist=self.window_hist),\
              GenerateIndicesDataset(sample_size=self.sample_size, filter_city=self.filter_city)

    def output(self):
      return luigi.LocalTarget(os.path.join(DATASET_DIR, clean_filename(self.filter_city), "train__explode_indexed__size=%d_window=%d.csv" % (self.sample_size, self.window_hist)))

    def most_popular_array(self, df):
      df_item = df.select("action_type_item_idx").toPandas()
      df_item = df_item.action_type_item_idx.value_counts()

      #df_item = df_item.to_dict()
      #df_array = csr_matrix((list(df_item.values), (np.zeros(len(df_item)), list(df_item.index))), shape=(1, np.max(list(df_item.index))+1)).toarray()[0] 
      return df_item.to_dict()

    def main(self, sc: SparkContext, *args):
      os.makedirs(DATASET_DIR, exist_ok=True)
      spark = SparkSession(sc)

      df            = spark.read.csv(self.input()[0].path, header=True, inferSchema=True)
      item_idx_df   = spark.read.csv(self.input()[1][0].path, header=True, inferSchema=True)
      item_idx_dict = item_idx_df.toPandas().set_index('item_id')['item_idx'].to_dict()
      item_idx_most_dict = self.most_popular_array(df)
      print(item_idx_most_dict)

      # Expand impressions interactions
      df = df.withColumn("impressions", to_array_int_udf(df.impressions)).\
              withColumn("prices", to_array_float_udf(df.prices))

      sort_array_by_dict = udf(lambda x: sorted(x, key=lambda _x: item_idx_most_dict[_x] if _x in item_idx_most_dict else 0 , reverse=True), ArrayType(IntegerType()))
      df = df.withColumn("list_mean_price", array_mean(df.prices))
      
      # Convert item_id to item_idx in impressions
      to_item_idx_from_dict_udf  = udf(lambda x: [item_idx_dict[i] if i in item_idx_dict else 0 for i in x], ArrayType(IntegerType()))
      df = df.withColumn("impressions", to_item_idx_from_dict_udf(df.impressions))
      df = df.withColumn("impressions_popularity", sort_array_by_dict(df.impressions))

      # Explode
      df = df.select("*", posexplode("impressions").alias("pos_item_idx", "item_idx"))


      df = df.withColumn("price", df["prices"].getItem(df.pos_item_idx)).\
              withColumn("popularity", df["impressions_popularity"].getItem(df.pos_item_idx)).\
              withColumn("clicked", when(df.action_type_item_idx == df.item_idx, 1.0).otherwise(0.0)).\
              withColumn("view", lit(1.0)).orderBy('timestamp')  

      df = df.withColumn("is_first_in_impression", df.pos_item_idx == lit(0))
      df = df.withColumn("first_item_idx", df["impressions"].getItem(lit(0)))
      df = df.withColumn("popularity_item_idx", df["impressions_popularity"].getItem(lit(0)))
      df = df.withColumn("diff_price", df.price - df.list_mean_price)

      # Quartile Discretize
      columns = ["price", "popularity"]
      for c in columns:
        discretizer = QuantileDiscretizer(numBuckets=4, inputCol=c, outputCol=c+"_BIN")
        df = discretizer.fit(df).transform(df)

      # add feature 'user_view', 'hist_views'
      win_user_item    = Window.partitionBy('user_idx', 'item_idx').orderBy('timestamp') \
                          .rangeBetween(Window.unboundedPreceding, -1)
      win_user         = Window.partitionBy('user_idx').orderBy('timestamp')\
                          .rangeBetween(Window.unboundedPreceding, -1)
            
      df = df.withColumn("user_view", F.sum(col("view")).over(win_user)).\
              withColumn("hist_views", F.sum(col("view")).over(win_user_item)).\
              fillna(0, subset=["user_view", "hist_views"])

      df = df.withColumn("user_view", df.user_view + lit(1)).\
              withColumn("hist_views", df.hist_views + lit(1))

      df = df.withColumn("ps", df.hist_views/df.user_view)
                           

      print(df.toPandas().head())
      df.orderBy('timestamp', "pos_item_idx").toPandas().to_csv(self.output().path, index=False)
      #sd

class PrepareTrivagoSessionsDataFrames(BasePrepareDataFrames):
    sample_size: int = luigi.IntParameter(default=-1)
    filter_city: str = luigi.Parameter(default='all')
    window_hist: int = luigi.IntParameter(default=5)

    def requires(self):
        return CreateExplodeWithNoClickIndexDataset(sample_size=self.sample_size, filter_city=self.filter_city, window_hist=self.window_hist),\
               CreateIndexDataset(sample_size=self.sample_size, filter_city=self.filter_city),\
               GenerateIndicesDataset(sample_size=self.sample_size, filter_city=self.filter_city), \
               TransformSessionDataset(sample_size=self.sample_size, filter_city=self.filter_city)

    @property
    def stratification_property(self) -> str:
        return "clicked"

    @property
    def timestamp_property(self) -> str:
        return "timestamp"

    @property
    def dataset_dir(self) -> str:
        return os.path.join(DATASET_DIR, clean_filename(self.filter_city))

    @property
    def vocab_size(self):
        if not hasattr(self, "_vocab_size"):
            self._vocab_size = len(pd.read_csv(self.input()[3][1].path))
        return self._vocab_size

    @property
    def num_users(self):
        if not hasattr(self, "_num_users"):
            accounts_df = pd.read_csv(self.input()[2][1].path)
            self._num_users = len(accounts_df)
        return self._num_users

    @property
    def num_businesses(self):
        if not hasattr(self, "_num_businesses"):
            businesses_df = pd.read_csv(self.input()[2][0].path)
            self._num_businesses = len(businesses_df)
        return self._num_businesses

    def read_data_frame(self) -> pd.DataFrame:
        if not hasattr(self, "_read_data_frame"):
            self._read_data_frame = pd.read_csv(self.input()[0].path)

        return self._read_data_frame

    @property
    def metadata_data_frame_path(self) -> str:
        return self.input()[1][1].path

    def transform_data_frame(self, df: pd.DataFrame, data_key: str) -> pd.DataFrame:
        # TODO

        df['n_users']          = self.num_users
        df['n_items']          = self.num_businesses
        df['clicked']          = df['clicked'].astype(float)
        df['is_first_in_impression']  = df['is_first_in_impression'].astype(float)
        df['vocab_size']       = self.vocab_size
        df['window_hist_size'] = self.window_hist

        if not hasattr(self, "_scaler"):
            self._scaler = MinMaxScaler()

        if len(df) > 1:
          if data_key == "TRAIN_DATA":
            df['diff_price'] = self._scaler.fit_transform(df[['diff_price']]).reshape(-1)

          elif data_key == "VALIDATION_DATA" or data_key == "TEST_GENERATOR":
            df['diff_price'] = self._scaler.transform(df[['diff_price']]).reshape(-1)
        


        return df        