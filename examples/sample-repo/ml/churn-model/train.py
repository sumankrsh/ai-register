"""Fine-tune a small text classifier on synthetic support tickets to predict churn."""

from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_name = "distilbert/distilbert-base-uncased"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

