FROM public.ecr.aws/lambda/python:3.12
COPY requirements.txt .
RUN pip install -r requirements.txt boto3
COPY rcv ./rcv
CMD ["rcv.lambda_handler.handler"]
