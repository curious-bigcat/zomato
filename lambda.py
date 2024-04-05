import json
import boto3
import pymongo
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

sagemaker_runtime_client = boto3.client("sagemaker-runtime")

def lambda_handler(event, context):
    try:
        # Extract the query parameter 'query' from the event
        query_param = event.get('queryStringParameters', {}).get('query', '')

        if query_param:
            embedding = get_embedding(query_param)
            search_results = perform_vector_search(embedding)

            # Prompt the user for their feedback on the search results
            user_prompt = f"Here are the search results for the query '{query_param}':\n\n{json.dumps(search_results, indent=2)}\n\n If the results are relevant to user's query, write a recommendation with 'name' 'cuisines' 'address' 'aggregate_rating' 'latitude' 'longitude', also provide 'latitude' 'longitude' in separate variable. else provide apology for unavaialability of data."

            # Invoke Claude 3 with the user prompt
            claude_response = invoke_claude_3_with_text(user_prompt)

            # Extract latitude and longitude from the search_quality_reflection
            search_quality_reflection = claude_response.get('content', [])
            if search_quality_reflection:
                for output in search_quality_reflection:
                    if 'latitude' in output and 'longitude' in output:
                        latitude = output.get('latitude')
                        longitude = output.get('longitude')
                        print(f"Latitude: {latitude}")
                        print(f"Longitude: {longitude}")
                    else:
                        print("Latitude and longitude not found in the search_quality_reflection.")

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'search_results': search_results,
                    'search_quality_reflection': claude_response
                })
            }
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No query parameter provided'})
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_embedding(synopsis):
    input_data = {"text_inputs": synopsis}
    response = sagemaker_runtime_client.invoke_endpoint(
        EndpointName="jumpstart-dft-hf-textembedding-all-minilm-l6-snow",
        Body=json.dumps(input_data),
        ContentType="application/json"
    )
    result = json.loads(response["Body"].read().decode())
    embedding = result["embedding"][0]
    return embedding

def perform_vector_search(embedding):
    # Connect to MongoDB Atlas
    client = pymongo.MongoClient("mongodb+srv://bharaths:Blippi123@restaurant.psa7j2k.mongodb.net/?retryWrites=true&w=majority&appName=restaurant")

    # Define pipeline for vector search
    pipeline = [
        {
            '$vectorSearch': {
                'index': 'vector_index',
                'path': 'embedding',
                'queryVector': embedding,
                'numCandidates': 200,
                'limit': 5
            }
        },
        {
            '$project': {
                '_id': 0,
                'name': 1,
                'type': 1,
                'cuisines': 1,
                'highlights': 1,
                'aggregate_rating': 1,
                'latitude': 1,
                'longitude': 1,
                'address': 1,
                'cuisine': 1,
                'timings': 1,
                'score': {
                    '$meta': 'vectorSearchScore'
                }
            }
        }
    ]
    
    # Run the pipeline
    result = client["zomato"]["restaurants"].aggregate(pipeline)
    
    # Convert the result to a list of dictionaries
    search_results = list(result)
    
    return search_results

def invoke_claude_3_with_text(prompt):
    """
    Invokes Anthropic Claude 3 Sonnet to run an inference using the input
    provided in the request body.

    :param prompt: The prompt that you want Claude 3 to complete.
    :return: Inference response from the model.
    """

    # Initialize the Amazon Bedrock runtime client
    client = boto3.client(
        service_name="bedrock-runtime", region_name="us-east-1"
    )

    # Invoke Claude 3 with the text prompt
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": prompt}],
                        }
                    ],
                }
            ),
        )

        # Process and print the response
        result = json.loads(response.get("body").read())
        input_tokens = result["usage"]["input_tokens"]
        output_tokens = result["usage"]["output_tokens"]
        output_list = result.get("content", [])

        #print("Invocation details:")
        #print(f"- The input length is {input_tokens} tokens.")
        #print(f"- The output length is {output_tokens} tokens.")

        #print(f"- The model returned {len(output_list)} response(s):")
        for output in output_list:
            print(output["text"])

        return result

    except ClientError as err:
        logger.error(
            "Couldn't invoke Claude 3 Sonnet. Here's why: %s: %s",
            err.response["Error"]["Code"],
            err.response["Error"]["Message"],
        )
        raise[]