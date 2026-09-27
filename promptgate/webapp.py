"""Local review console. No prompt or credential is written to a file or access log."""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .contracts import ContractError
from .explanation import explain_review
from .ml import Detector

STATIC = Path(__file__).parent / 'static' / 'index.html'


class Input(BaseModel):
    prompt: str = Field(min_length=1,max_length=8000)
    model: str = 'naive_bayes'


class ExplainInput(Input):
    api_key: str = Field(default='',max_length=200)


def create_app(models_dir: Path = Path('models/teacher-11089')):
    detectors={name:Detector(models_dir,name) for name in ('naive_bayes','logistic_word_char')}
    app=FastAPI(title='PromptGate',version='0.2.0',docs_url=None,redoc_url=None)

    def decide(entry):
        if entry.model not in detectors:
            raise HTTPException(400,'Unknown model.')
        try:
            return detectors[entry.model].screen(entry.prompt,hybrid=True)
        except ContractError as exc:
            raise HTTPException(400,str(exc)) from exc

    @app.get('/',response_class=HTMLResponse)
    def home():
        return STATIC.read_text(encoding='utf-8')

    @app.get('/health')
    def health():
        return {'status':'ready','models':list(detectors),'data_collection':'none'}

    @app.post('/screen')
    def screen(entry:Input):
        result=decide(entry)
        response=result.public_dict()
        response['review_required']=result.action=='Review'
        return response

    @app.post('/explain-review')
    def explain(entry:ExplainInput):
        result=decide(entry)
        if result.action!='Review':
            raise HTTPException(409,'This prompt is not a Review case; explanation call not made.')
        return explain_review(entry.prompt,entry.api_key)

    return app


def main():
    import argparse
    import uvicorn
    parser=argparse.ArgumentParser()
    parser.add_argument('--models',type=Path,default=Path('models/teacher-11089'))
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    uvicorn.run(create_app(args.models),host='127.0.0.1',port=args.port,access_log=False)


if __name__=='__main__':
    main()
