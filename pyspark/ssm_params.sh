aws ssm put-parameter \
  --name /kafka_spark_demo/kafka_servers \
  --type String \
  --value "<b-1.your-brokers,b-2.your-brokers,...>" \
  --description "Amazon MSK Kafka broker list" \
  --overwrite

aws ssm put-parameter \
  --name /kafka_spark_demo/kafka_demo_bucket \
  --type String \
  --value "<your-bucket-111222333444-us-east-1>" \
  --description "Amazon S3 bucket" \
  --overwrite

# added for avro/schema registry demo
aws ssm put-parameter \
  --name /kafka_spark_demo/schema_resistry_url_int \
  --type String \
  --value "http://<your_host>:<your_port>" \
  --description "Apicurio Registry REST API base URL (Internal IP Address)" \
  --overwrite

aws ssm put-parameter \
  --name /kafka_spark_demo/schema_registry_url_ext \
  --type String \
  --value "http://<your_host>:<your_port>" \
  --description "Apicurio Registry REST API base URL (external IP Address)" \
  --overwrite
