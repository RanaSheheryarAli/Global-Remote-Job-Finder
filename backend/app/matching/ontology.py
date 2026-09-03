from __future__ import annotations

import re

SKILL_CATEGORIES: dict[str, dict[str, tuple[str, ...]]] = {
    "languages": {
        "JavaScript": ("javascript",),
        "TypeScript": ("typescript",),
        "Python": ("python",),
        "PHP": ("php",),
        "Java": ("java",),
        "Swift": ("swift",),
        "Kotlin": ("kotlin",),
        "Objective-C": ("objective-c", "objective c"),
    },
    "frontend": {
        "React": ("react", "react.js", "reactjs"),
        "Next.js": ("next.js", "nextjs"),
        "Angular": ("angular", "angularjs"),
        "Vue.js": ("vue.js", "vuejs", "vue"),
        "Nuxt.js": ("nuxt.js", "nuxtjs", "nuxt"),
        "React Native": ("react native",),
        "HTML": ("html", "html5"),
        "CSS": ("css", "css3"),
        "Tailwind CSS": ("tailwind", "tailwind css"),
        "Bootstrap": ("bootstrap",),
    },
    "backend": {
        "Node.js": ("node.js", "nodejs", "node"),
        "Express.js": ("express.js", "expressjs", "express"),
        "NestJS": ("nestjs", "nest.js"),
        "FastAPI": ("fastapi",),
        "Laravel": ("laravel",),
        "REST APIs": ("rest api", "restful api", "rest/json"),
    },
    "data": {
        "PostgreSQL": ("postgresql", "postgres"),
        "MySQL": ("mysql",),
        "MongoDB": ("mongodb", "mongo db"),
        "DynamoDB": ("dynamodb", "dynamo db"),
        "Redis": ("redis",),
        "SQL Server": ("sql server", "mssql"),
        "Vector databases": ("vector database", "vector db", "chromadb"),
    },
    "messaging": {
        "Kafka": ("kafka", "apache kafka"),
        "RabbitMQ": ("rabbitmq",),
        "AWS SQS": ("aws sqs", "sqs"),
        "AWS SNS": ("aws sns", "sns"),
    },
    "cloud_devops": {
        "AWS": ("aws", "amazon web services"),
        "Azure": ("azure", "microsoft azure"),
        "GCP": ("gcp", "google cloud", "google cloud platform"),
        "Docker": ("docker",),
        "Kubernetes": ("kubernetes", "k8s"),
        "Terraform": ("terraform",),
        "CI/CD": ("ci/cd", "continuous integration", "continuous delivery"),
        "GitHub": ("github",),
    },
    "ai": {
        "LLM": ("llm", "large language model"),
        "RAG": ("rag", "retrieval augmented generation"),
        "LangChain": ("langchain",),
        "LangGraph": ("langgraph",),
        "Hugging Face": ("hugging face", "huggingface"),
        "OpenAI API": ("openai api", "openai"),
        "Embeddings": ("embedding", "embeddings"),
        "AI agents": ("ai agent", "agents"),
        "Demucs": ("demucs",),
        "Librosa": ("librosa",),
        "Speech-to-text": ("speech-to-text", "speech recognition"),
        "Text-to-speech": ("text-to-speech",),
    },
    "observability_security": {
        "ELK Stack": ("elk stack", "elasticsearch logstash kibana"),
        "Datadog": ("datadog",),
        "CloudWatch": ("cloudwatch",),
        "Sentry": ("sentry",),
        "PostHog": ("posthog",),
        "OAuth2": ("oauth2", "oauth 2"),
        "JWT": ("jwt",),
        "RBAC": ("rbac", "role-based access control"),
    },
}

DOMAIN_ALIASES = {
    "healthcare": ("healthcare", "clinical", "patient", "provider"),
    "real_estate": ("real estate", "real-estate", "property", "properties"),
    "document_intelligence": ("document intelligence", "document processing", "pdf"),
    "audio_ai": ("audio", "speech", "music", "voice recognition"),
    "crm": ("crm", "customer relationship", "lead assignment"),
    "mobile_apps": ("mobile application", "ios", "android", "app store", "google play"),
}

ARCHITECTURE_ALIASES = {
    "distributed_systems": ("distributed system",),
    "microservices": ("microservice",),
    "event_driven": ("event-driven", "event driven"),
    "system_design": ("system design", "architecture"),
    "scalability": ("scalable", "high-performance", "high performance"),
}


def _contains(text: str, alias: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(alias.casefold())}(?![a-z0-9])"
    return re.search(pattern, text.casefold()) is not None


def extract_skills(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for category, definitions in SKILL_CATEGORIES.items():
        found = [
            skill
            for skill, aliases in definitions.items()
            if any(_contains(text, alias) for alias in aliases)
        ]
        if found:
            result[category] = found
    return result


def flatten_skills(skills: dict[str, list[str]]) -> set[str]:
    return {skill for values in skills.values() for skill in values}


def extract_named_traits(text: str, definitions: dict[str, tuple[str, ...]]) -> list[str]:
    return [
        name
        for name, aliases in definitions.items()
        if any(_contains(text, alias) for alias in aliases)
    ]
