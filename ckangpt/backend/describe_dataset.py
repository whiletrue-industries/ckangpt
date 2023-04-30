import json
import csv
from io import StringIO

from typing import Any, Dict

from textwrap import dedent

from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.callbacks import get_openai_callback

from ckangpt.utils.datasets import get_dataset

import dataflows as DF


class DatasetPrompt(PromptTemplate):

    dataset: Dict[str, Any]
    """The dataset to describe"""

    def format(self, **kwargs):
        dataset = self.dataset
        resources = [
            f"{resource.get('name', '').strip()}:\n{resource['sample']}"
            for resource in dataset.get('resources', [])
        ]
        res = filter(None, [
            f"Title: {dataset['title'].strip()}",
            f"Notes: {dataset['notes'].strip()[:200]}" if dataset.get('notes') else None,
            f"Organization: {dataset['organization']['title'].strip()}" if dataset.get('organization', {}).get('title') else None,
            f"Organization description: {dataset['organization']['description'].strip()}" if dataset.get('organization', {}).get('description') else None,
            f"Dataset files and sample data in CSV format:\n" + '\n\n'.join(f'{i+1}) {resource}' for i, resource in enumerate(resources)) if resources else None,
        ])
        kwargs['text'] = '\n'.join(res)
        return super().format(**kwargs)

def fetch_dataset_data(dataset):
    resources = []
    for resource in dataset.get('resources').values():
        if 'format' not in resource:
            continue
        if resource['format'].lower() in ['csv', 'xls', 'xlsx']:
            if 'url' not in resource:
                continue
            url = resource['url']
            try:
                print('Loading', url)
                data, df, _ = DF.Flow(
                    DF.load(url, limit_rows=5),
                ).results()
                resource['data'] = data[0]
                resource['fields'] = df.descriptor['resources'][0]['schema']['fields']
                out = StringIO()
                writer = csv.DictWriter(out, fieldnames=[f['name'] for f in resource['fields']])
                writer.writeheader()
                for row in resource['data']:
                    writer.writerow(row)
                resource['sample'] = out.getvalue()
                resources.append(resource)
            except Exception as e:
                print('Failed to load', url, e)
                resource['sample'] = url
    dataset['resources'] = resources


def main(dataset_id, gpt4=False):
    if gpt4:
        print('WARNING! Using GPT-4 - this will be slow and expensive!')
    dataset = json.loads(get_dataset(dataset_id))
    fetch_dataset_data(dataset)
    chain = LLMChain(
        llm=ChatOpenAI(model_name='gpt-4' if gpt4 else 'gpt-3.5-turbo', request_timeout=240),
        prompt=DatasetPrompt(input_variables=['text'], template_format='jinja2', template=dedent("""
            Following are details on a dataset containing public data. Provide a summary of this dataset in JSON format, including a title, description, and keywords. The JSON should look like this:
            {
                "purpose": "<What is the purpose of this dataset? A single sentence, concise and descriptive, using simple terms and avoiding jargon.>",
                "description": "<A good description of this dataset in a single paragraph, using simple terms and avoiding jargon.>",
                "keywords": "<a semicolon-separated list of keywords that describe this dataset>",
                "data": "<What sort of data might we find in this dataset?>"
            }
            ----------------
            {{text}}
        """), dataset=dataset),
        verbose=True
    )
    with get_openai_callback() as cb:
        res = chain.run(dataset_id)
        print(cb)
    return(res)