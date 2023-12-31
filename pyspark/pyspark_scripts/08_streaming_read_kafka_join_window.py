import os

import boto3
import pyspark.sql.functions as F
from ec2_metadata import ec2_metadata
from pyspark.sql import SparkSession
from pyspark.sql.types import StructField, StructType, IntegerType, \
    StringType, FloatType, TimestampType

topic_input = "pagila.sales.spark.streaming.region"
regions_data = "sales_regions.csv"

os.environ['AWS_DEFAULT_REGION'] = ec2_metadata.region
ssm_client = boto3.client("ssm")


def main():
    params = get_parameters()

    spark = SparkSession \
        .builder \
        .appName("kafka-streaming-sales-join") \
        .getOrCreate()

    df_regions = read_from_csv(spark, params)
    df_regions.cache()

    df_sales = read_from_kafka(spark, params)
    summarize_sales(df_sales, df_regions)


def read_from_kafka(spark, params):
    options_read = {
        "kafka.bootstrap.servers":
            params["kafka_servers"],
        "subscribe":
            topic_input,
        "startingOffsets":
            "earliest",
        "kafka.ssl.truststore.location":
            "/tmp/kafka.client.truststore.jks",
        "kafka.security.protocol":
            "SASL_SSL",
        "kafka.sasl.mechanism":
            "AWS_MSK_IAM",
        "kafka.sasl.jaas.config":
            "software.amazon.msk.auth.iam.IAMLoginModule required;",
        "kafka.sasl.client.callback.handler.class":
            "software.amazon.msk.auth.iam.IAMClientCallbackHandler"
    }

    df_sales = spark.readStream \
        .format("kafka") \
        .options(**options_read) \
        .load()

    return df_sales


def read_from_csv(spark, params):
    schema = StructType([
        StructField("country", StringType(), False),
        StructField("region", StringType(), False)
    ])

    df_sales = spark.read \
        .csv(path=f"s3a://{params['kafka_demo_bucket']}/spark/{regions_data}",
             schema=schema, header=True, sep=",")

    return df_sales


def summarize_sales(df_sales, df_regions):
    schema = StructType([
        StructField("payment_id", IntegerType(), False),
        StructField("customer_id", IntegerType(), False),
        StructField("amount", FloatType(), False),
        StructField("payment_date", TimestampType(), False),
        StructField("city", StringType(), True),
        StructField("district", StringType(), True),
        StructField("country", StringType(), False),
    ])

    ds_sales = df_sales \
        .selectExpr("CAST(value AS STRING)", "timestamp") \
        .select(F.from_json("value", schema=schema).alias("data"), "timestamp") \
        .select("data.*", "timestamp") \
        .join(df_regions, on=["country"], how="leftOuter") \
        .na.fill("Unassigned") \
        .withWatermark("timestamp", "10 minutes") \
        .groupBy("region", F.window("timestamp", "10 minutes", "5 minutes")) \
        .agg(F.sum("amount"), F.count("amount")) \
        .orderBy(F.col("window").desc(), F.col("sum(amount)").desc()) \
        .select(F.col("region").alias("sales_region"),
                F.format_number("sum(amount)", 2).alias("sales"),
                F.col("count(amount)").alias("orders"),
                F.from_unixtime("window_start", format="yyyy-MM-dd HH:mm").alias("window_start"),
                F.from_unixtime("window_end", format="yyyy-MM-dd HH:mm").alias("window_end")) \
        .coalesce(1) \
        .writeStream \
        .queryName("streaming_regional_sales") \
        .trigger(processingTime="1 minute") \
        .outputMode("complete") \
        .format("console") \
        .option("numRows", 24) \
        .option("truncate", False) \
        .start()

    ds_sales.awaitTermination()


def get_parameters():
    """Load parameter values from AWS Systems Manager (SSM) Parameter Store"""

    params = {
        "kafka_servers": ssm_client.get_parameter(
            Name="/kafka_spark_demo/kafka_servers")["Parameter"]["Value"],
        "kafka_demo_bucket": ssm_client.get_parameter(
            Name="/kafka_spark_demo/kafka_demo_bucket")["Parameter"]["Value"],
    }

    return params


if __name__ == "__main__":
    main()
