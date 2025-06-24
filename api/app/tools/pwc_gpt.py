import aiohttp
import json
import asyncio
from typing import List, Dict, Optional, Any, Union, AsyncGenerator
from ..config import LITELLM_URL, LITELLM_KEY


class AsyncPwCGPTModel:
    """비동기(async) 방식으로 GPT 모델을 호출하는 클래스."""
    
    def __init__(self, default_model_name: str, logger=None):
        self.default_model = default_model_name
        self.base_url = LITELLM_URL
        self.api_key = LITELLM_KEY
        self.logger = logger
        
        # Django 환경에서 사용할 경우의 주석 처리된 코드
        # self.base_url = env("LITELLM_URL", default="https://genai-sharedservice-americas.pwcinternal.com")
        # self.api_key = env("LITELLM_KEY")
        
    async def health_check(self) -> int:
        """
        비동기적으로 API 서버 상태를 확인합니다.
        """
        if self.logger is not None: 
            self.logger.info("PWC Health Check")
            
        url = self.base_url + "/models"
        headers = {
            'accept': 'application/json',
            'Authorization': 'Bearer ' + self.api_key,
        }
        # 아래 주석은 pwc-gpt v1일때의 방식 archive
        # url = self.base_url + "/healthz"
        # headers = {
        #     "Accept": "*/*",
        #     "Accept-Encoding": "gzip, deflate, br",
        #     "Connection": "keep-alive", 
        #     "Authorization": self.bearer_auth,
        #     "Ocp-Apim-Subscription-Key": self.api_key,
        # }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                status_code = response.status
                if self.logger is not None:
                    self.logger.info(f"Health Check Status code : {status_code}")
                print(f"Health Check Status code : {status_code}")
                
                return status_code
                
    async def run(
        self,
        messages: Union[List[Dict], Dict],
        model: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 1.0,
        top_p: float = 1.0,
        n: int = 1,
        **kwargs
    ) -> str:
        """
        비동기적으로 GPT 모델에 요청을 보내고 응답을 받습니다.
        
        Args:
            messages: 대화 메시지 목록 또는 단일 메시지
            model: 사용할 모델 (기본값: 초기화 시 설정된 모델)
            max_retries: 최대 재시도 횟수
            temperature: 응답 다양성 조절 파라미터
            top_p: 토큰 샘플링 파라미터
            n: 생성할 응답 수
            **kwargs: 추가 매개변수 (max_tokens, response_format 등)
            
        Returns:
            모델의 응답 텍스트
        """
        url = self.base_url + "/chat/completions"
        
        headers = {
            "User-Agent": "curl/8.9.1",
            # "user-agent": "got (https://github.com/sindresorhus/got)",
            "accept": "application/json",
            # "content-length": "343",
            "accept-encoding": "gzip, deflate, br",
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            # "API-Key": self.api_key,      
            "Connection": "keep-alive",  
            "x-request-type": "sync",
        }
        
        model_name = self.default_model if model is None else model
        # 단일 메시지인 경우 리스트로 변환 (API 호환성 보장)
        if isinstance(messages, dict):  messages = [messages]
        body = {
            "temperature": temperature,
            "top_p": top_p,
            "n": n,
            "stream": False,
            "messages": messages,
            "model": model_name,
        }
        # pwc-1106v에서는 default가 16인 버그가있어서 수동으로 지정
        if "max_tokens" not in kwargs and "1106v" in model_name:
            kwargs["max_tokens"] = 4096
        # kwargs로 전달된 추가 매개변수 적용
        body.update(kwargs)
        
        # print(messages)

        # 메시지 길이 계산 - 중첩 구조 지원
        def get_content_length(item):
            if isinstance(item, str):
                return len(item)
            elif isinstance(item, dict):
                # 일반적인 text content
                if "text" in item:
                    return len(item["text"])
                # content 키가 있는 경우
                elif "content" in item:
                    return get_content_length(item["content"])
                # image_url이 있는 경우
                elif "image_url" in item and isinstance(item["image_url"], dict) and "url" in item["image_url"]:
                    return len(item["image_url"]["url"])
                # 다른 모든 문자열 값 합산
                else:
                    return sum(get_content_length(v) for k, v in item.items() if isinstance(v, (str, dict, list)))
            elif isinstance(item, list):
                return sum(get_content_length(subitem) for subitem in item)
            return 0
        
        message_lengths = [get_content_length(message) for message in messages]
        print("(AsyncPWCGPTModel.run)###MESSAGE LENGTH:", message_lengths)       
        # print("###MESSAGE LENGTH:", [len(message["content"]) for message in messages])
                
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=body,
                    ssl=False,
                    allow_redirects=True
                ) as response:
                    if response.status == 400:
                        raise ValueError("Maybe the input token size is too big")
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # print("###RESPONSE", data)
                        result = data["choices"][0]["message"]["content"]                      
                        if self.logger is not None:
                            self.logger.info(f"GPT Response: {result}")                            
                        return result
                    else:
                        error_text = await response.text()
                        raise Exception(f"Error: {response.status}, {error_text}")
                        
        except Exception as e:
            print(f"Inner PWC-GPT Error: {e} in thread")
            if max_retries > 0:
                if self.logger is not None:
                    self.logger.info(f"Retrying... ({max_retries} retries left)")
                print(f"Retrying... ({max_retries} retries left)")
                await asyncio.sleep(1)
                
                # 앞에서 이미 계산한 길이를 사용 - 중첩 구조와 단일/목록 형식 모두 지원
                input_prompt_len = sum(message_lengths)
                if input_prompt_len > 16384 * 1.6:
                    # self.model_name = "bedrock.anthropic.claude-3-5-sonnet"
                    print(f"Actually the token size was bigger than as expected: {input_prompt_len}")
                    return await self.run(
                        messages, 
                        model="bedrock.anthropic.claude-3-5-sonnet", 
                        max_retries=max_retries - 1,
                        temperature=temperature,
                        top_p=top_p,
                        n=n,
                        **kwargs
                    )
                else:
                    return await self.run(
                        messages,
                        model=model,
                        max_retries=max_retries - 1,
                        temperature=temperature,
                        top_p=top_p,
                        n=n,
                        **kwargs
                    )
            else:
                if self.logger is not None:
                    self.logger.error("Maximum retries exceeded. Exiting.")
                raise Exception("Process killed - Maximum retries exceeded")
    
    async def process_batch(self, batch, process_all_batches=False, max_retries=3, backoff_factor=10, **kwargs):
        """
        여러 요청을 비동기적으로 처리합니다.
        
        Args:
            batch: 처리할 요청 목록 (각 요청은 딕셔너리)
            process_all_batches: True면 모든 배치 요청 처리, False면 첫 번째 요청만 처리
            max_retries: 최대 재시도 횟수
            backoff_factor: 재시도 사이의 대기 시간(초)
            **kwargs: run 메서드에 전달할 추가 매개변수
            
        Returns:
            처리 결과 목록
        """
        results = []

        try:
            #######################################################
            ### Single thread can process the batch : list of data_dict
            ### But it requires PWCAzureAgent, not simple requests.post
            ### Thus, current version of batch(list) contains only one data_dict
            ######################2024/04/25#######################
            messages = [data_dict["messages"] for data_dict in batch]
            ids = [data_dict["id"] for data_dict in batch]
            model_names = [data_dict.get("model_name", self.default_model) for data_dict in batch]
            
            if len(messages) > 1 and not process_all_batches:
                print(
                    "batch size is bigger than 1, only one data_dict can be processed now"
                )
                # process_all_batches=False면 첫 번째 요청만 처리
                response = await self.run(messages[0], model_names[0], **kwargs)
                responses = [response]
            else:
                # process_all_batches=True면 모든 요청 병렬 처리
                tasks = []
                for i, msg in enumerate(messages):
                    tasks.append(self.run(msg, model_names[i], **kwargs))
                
                responses = await asyncio.gather(*tasks)

            for response, id in zip(responses, ids):
                result = {id: response}
                results.append(result)

        except Exception as e:
            print(f"Outer Async PWCGPT API Error: {e}")
            if max_retries > 0:
                print(f"Reloading the authentication token...")
                await asyncio.sleep(backoff_factor)
                                
                return await self.process_batch(
                    batch, 
                    process_all_batches=process_all_batches,
                    max_retries=max_retries - 1, 
                    backoff_factor=backoff_factor,
                    **kwargs
                )
            else:
                print("Exiting.")
                raise Exception("Process killed")

        return results
    async def run_stream(
        self,
        messages: Union[List[Dict], Dict],
        model: Optional[str] = None,
        temperature: float = 1.0,
        top_p: float = 1.0,
        n: int = 1,
        **kwargs
    ) -> AsyncGenerator[Dict, None]:
        """
        비동기적으로 GPT 모델에 요청을 보내고 스트리밍 응답을 생성합니다.
        
        Args:
            messages: 메시지 목록 또는 단일 메시지
            model: 사용할 모델 (기본값: 초기화 시 설정된 모델)
            temperature: 응답 다양성 조절 파라미터
            top_p: 토큰 샘플링 파라미터
            n: 생성할 응답 수
            **kwargs: 추가 매개변수 (max_tokens 등)
            
        Yields:
            응답 청크. 형식: {"choices": [{"delta": {"content": "청크 내용"}}]}
        """
        # 단일 메시지인 경우 리스트로 변환
        if isinstance(messages, dict):
            messages = [messages]
        
        url = self.base_url + "/chat/completions"
        
        headers = {
            "User-Agent": "curl/8.9.1",
            "accept": "application/json",
            "accept-encoding": "gzip, deflate, br",
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "x-request-type": "sync",
        }
        
        body = {
            "temperature": temperature,
            "top_p": top_p,
            "n": n,
            "stream": True,
            "messages": messages,
            "model": self.default_model if model is None else model,
        }
        
        body.update(kwargs)
        
        print("(AsyncPWCGPTModel.run_stream)###MESSAGE LENGTH:", [len(message["content"]) for message in messages])
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=body,
                    ssl=False,
                    allow_redirects=True
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        error_msg = f"Error: {response.status}, {error_text}"
                        yield {"choices": [{"delta": {"content": error_msg}}]}
                        return
                    
                    # 스트리밍 응답 처리
                    async for line in response.content:
                        if not line:
                            continue
                        
                        try:
                            line_text = line.decode('utf-8').strip()
                            
                            # 데이터 라인 확인
                            if line_text.startswith("data: "):
                                data_content = line_text[6:]
                                
                                # 스트림 종료 확인
                                if data_content == "[DONE]":
                                    break
                                
                                # JSON 파싱
                                try:
                                    json_data = json.loads(data_content)
                                    
                                    if "choices" in json_data and len(json_data["choices"]) > 0:
                                        choice = json_data["choices"][0]
                                        
                                        if "delta" in choice and "content" in choice["delta"]:
                                            content = choice["delta"]["content"]
                                            
                                            # 청크 반환
                                            yield {"choices": [{"delta": {"content": content}}]}
                                except json.JSONDecodeError as je:
                                    print(f"JSON decode error: {je}, content: {data_content[:100]}")
                                    continue
                        except Exception as line_error:
                            print(f"Error processing line: {line_error}")
                            yield {"choices": [{"delta": {"content": f"Error processing response: {str(line_error)}"}}]}
                    
        except Exception as e:
            print(f"Stream Error: {e}")
            yield {"choices": [{"delta": {"content": f"Error in stream: {str(e)}"}}]}
    
# 독립 실행용 테스트 (Django 환경 외부에서 실행 가능)
async def run_standalone_test():
    """
    Django 환경 외부에서 독립적으로 실행 가능한 테스트
    
    시나리오 1: model.run 직접 사용
    시나리오 2: model.process_batch 사용
    """
    print("=== AsyncPwCGPTModel 독립 테스트 시작 ===")
    
    from ..log_generator import Log
    # 모델 초기화
    model = AsyncPwCGPTModel("azure.gpt-4o", 
                             logger=Log().logger) #logger timestamp로 비동기실행 보다 입체적으로 확인 가능
    
    # 5개의 테스트 질문 (간결한 버전)
    test_questions = [
        "Python의 특징은?",
        "비동기 프로그래밍이란?",
        "REST API란?",
        "Docker란?",
        "AI란?"
    ]
    
    # 시나리오 1: model.run 직접 사용
    print("\n시나리오 1: model.run 테스트")
    try:
        run_tasks = []
        for question in test_questions:
            messages = [
                {"role": "system", "content": "간결하게 대답해주세요."},
                {"role": "user", "content": question}
            ]
            run_tasks.append(model.run(messages, max_tokens=50))
        
        run_results = await asyncio.gather(*run_tasks)
        
        print(f"응답 수: {len(run_results)}")
        for i, result in enumerate(run_results):
            print(f"질문 {i+1} 응답: {result[:50]}...")
        print("✓ 시나리오 1 성공")
    except Exception as e:
        print(f"✗ 시나리오 1 실패: {e}")
    
    # 시나리오 2: model.process_batch 사용
    print("\n시나리오 2: model.process_batch 테스트")
    try:
        # 배치 요청 준비
        batch_requests = []
        for i, question in enumerate(test_questions):
            batch_requests.append({
                "id": f"q{i+1}",
                "messages": [
                    {"role": "system", "content": "간결하게 대답해주세요."},
                    {"role": "user", "content": question}
                ]
            })
        
        batch_results = await model.process_batch(
            batch_requests, 
            process_all_batches=True,
            max_tokens=50
        )
        
        print(f"응답 수: {len(batch_results)}")
        for result in batch_results:
            for id, content in result.items():
                print(f"{id}: {content[:50]}...")
        print("✓ 시나리오 2 성공")
    except Exception as e:
        print(f"✗ 시나리오 2 실패: {e}")
    
    print("\n=== 테스트 완료 ===")

async def test_console_streaming():
    import time, sys
    """
    콘솔에서 run_stream 함수를 테스트합니다.
    스트리밍 출력을 콘솔에 실시간으로 표시합니다.
    """
    print("=== 콘솔 스트리밍 테스트 시작 ===")
    
    # 모델 초기화
    model = AsyncPwCGPTModel("azure.gpt-4o")
    
    # 테스트 메시지
    messages = [
        {"role": "system", "content": "당신은 프로그래밍 전문가입니다. 간결하고 명확하게 응답해주세요."},
        {"role": "user", "content": "비동기 프로그래밍에 대해 설명하고, Python asyncio의 주요 기능 3가지를 알려주세요."}
    ]
    
    print("\n질문: 비동기 프로그래밍에 대해 설명하고, Python asyncio의 주요 기능 3가지를 알려주세요.\n")
    print("응답 스트리밍 중...")
    print("-" * 50)
    
    start_time = time.time()
    full_response = ""
    
    try:
        async for chunk in model.run_stream(messages, max_tokens=300):
            if "choices" in chunk and len(chunk["choices"]) > 0:
                content = chunk["choices"][0]["delta"].get("content", "")
                if content:
                    # 실시간으로 콘솔에 출력
                    sys.stdout.write(content)
                    sys.stdout.flush()
                    full_response += content
    except Exception as e:
        print(f"\n\n오류 발생: {e}")
    
    elapsed_time = time.time() - start_time
    
    print("\n" + "-" * 50)
    print(f"스트리밍 완료 (소요시간: {elapsed_time:.2f}초)")
    print(f"총 응답 길이: {len(full_response)} 자")
    print("=== 콘솔 스트리밍 테스트 종료 ===")

async def test_parallel_console_streaming():
    import time, os
    """
    2개의 요청을 병렬로 스트리밍하고 콘솔에 실시간으로 출력합니다.
    각 요청은 다른 색상으로 구분됩니다.
    """
    # ANSI 색상 코드 (Windows/Linux 호환)
    COLOR_RESET = '\033[0m'
    COLOR_RED = '\033[91m'
    COLOR_GREEN = '\033[92m'
    COLOR_BLUE = '\033[94m'
    COLOR_MAGENTA = '\033[95m' 
    COLOR_YELLOW = '\033[93m'

    # Windows에서 ANSI 색상 활성화
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    
    print(f"{COLOR_YELLOW}=== 병렬 콘솔 스트리밍 테스트 시작 ==={COLOR_RESET}")
    
    # 모델 초기화
    model = AsyncPwCGPTModel("azure.gpt-4o")
    
    # 테스트 메시지
    messages1 = [
        {"role": "system", "content": "당신은 프로그래밍 전문가입니다. 간결하게 답변해주세요."},
        {"role": "user", "content": "비동기 프로그래밍의 주요 장점을 설명해주세요."}
    ]
    
    messages2 = [
        {"role": "system", "content": "당신은 프로그래밍 전문가입니다. 간결하게 답변해주세요."},
        {"role": "user", "content": "멀티스레딩과 비동기 프로그래밍의 차이점은 무엇인가요?"}
    ]
    
    messages3 = [
        {"role": "system", "content": "당신은 프로그래밍 전문가입니다. 간결하게 답변해주세요."},
        {"role": "user", "content": "Python에서 asyncio 라이브러리의 주요 기능은 무엇인가요?"}
    ]
    
    print(f"\n{COLOR_BLUE}[질문 1]{COLOR_RESET} 비동기 프로그래밍의 주요 장점을 설명해주세요.")
    print(f"{COLOR_GREEN}[질문 2]{COLOR_RESET} 멀티스레딩과 비동기 프로그래밍의 차이점은 무엇인가요?")
    print(f"{COLOR_MAGENTA}[질문 3]{COLOR_RESET} Python에서 asyncio 라이브러리의 주요 기능은 무엇인가요?\n")
    print("=" * 80)
    print("병렬 스트리밍 응답 (세 응답이 섞여서 출력됩니다):")
    print("-" * 80)
    
    # 시작 시간 기록
    start_time = time.time()
    
    # 스트리밍 처리 비동기 함수
    async def process_stream(messages, question_id, color):
        try:
            # 요청 간에 약간의 시차를 두어 출력이 더 잘 섞이도록 함
            await asyncio.sleep(0.05 * (question_id - 1))
            
            # 스트리밍 시작
            chunk_count = 0
            
            # 비동기 스트리밍
            async for chunk in model.run_stream(messages, max_tokens=200):
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    content = chunk["choices"][0]["delta"].get("content", "")
                    if content:
                        chunk_count += 1
                        elapsed = time.time() - start_time
                        
                        # 콘솔에 직접 출력
                        print(f"{color}[{elapsed:.2f}s][질문 {question_id}]{COLOR_RESET} {content}", end="", flush=True)
                        
                        # 잠시 대기하여 다른 스트림과 교차될 기회 제공
                        await asyncio.sleep(0.01)
        except Exception as e:
            print(f"{COLOR_RED}[오류][질문 {question_id}] {str(e)}{COLOR_RESET}\n")
    
    # 세 스트림을 동시에 처리
    tasks = [
        asyncio.create_task(process_stream(messages1, 1, COLOR_BLUE)),
        asyncio.create_task(process_stream(messages2, 2, COLOR_GREEN)),
        asyncio.create_task(process_stream(messages3, 3, COLOR_MAGENTA))
    ]
    
    # 모든 태스크 완료 대기
    await asyncio.gather(*tasks)
    
    # 완료 시간 계산
    elapsed_time = time.time() - start_time
    
    print("\n" + "-" * 80)
    print(f"{COLOR_YELLOW}병렬 스트리밍 완료 (소요시간: {elapsed_time:.2f}초){COLOR_RESET}")
    print("=" * 80)
    print(f"{COLOR_YELLOW}=== 병렬 콘솔 스트리밍 테스트 종료 ==={COLOR_RESET}")

# 독립 실행을 위한 코드
if __name__ == "__main__":
    # asyncio.run(run_standalone_test())
    # asyncio.run(test_console_streaming())
    asyncio.run(test_parallel_console_streaming())