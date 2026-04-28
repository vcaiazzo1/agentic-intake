import anthropic

MODEL = "us.anthropic.claude-sonnet-4-20250514-v1:0"

client = anthropic.AnthropicBedrock(
    aws_profile="bootcamp",
    aws_region="us-east-1",
)


def test():
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": "hello"}],
    )
    for block in response.content:
        if block.type == "text":
            print(block.text)


if __name__ == "__main__":
    test()
