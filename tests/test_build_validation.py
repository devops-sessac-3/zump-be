"""
빌드 검증을 위한 단위테스트
이 테스트는 코드가 정상적으로 빌드되고 실행될 수 있는지 확인합니다.
"""
import pytest
import sys
import os
from pathlib import Path
import ast
import importlib.util

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestBuildValidation:
    """빌드 검증 테스트 클래스"""
    
    def test_python_syntax_validation(self):
        """Python 파일들의 문법이 올바른지 테스트"""
        python_files = [
            "main.py",
            "engines/user_engine.py",
            "engines/concert_engine.py",
            "queries/user_query.py", 
            "queries/concert_query.py",
            "routers/user_router.py",
            "routers/concert_router.py",
            "routers/queue_router.py",
            "routers/enqueue_router.py",
            "schemas/user_schema.py",
            "schemas/concert_schema.py",
            "utils/config.py",
            "utils/database.py",
            "utils/exception.py",
            "utils/kafka_client.py",
            "utils/redis_client.py",
            "utils/scheduler.py",
            "utils/security.py",
            "utils/sse.py",
            "utils/queue_notifier.py",
            "utils/rank_subscriber.py",
            "workers/worker.py",
            "workers/concert_queue_worker.py"
        ]
        
        for file_path in python_files:
            full_path = project_root / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        source = f.read()
                    
                    # AST 파싱으로 문법 검사
                    ast.parse(source)
                    
                except SyntaxError as e:
                    pytest.fail(f"{file_path} 문법 오류: {e}")
                except Exception as e:
                    pytest.fail(f"{file_path} 읽기 오류: {e}")
    
    def test_import_structure_validation(self):
        """import 구조가 올바른지 테스트"""
        # main.py의 import 구조 검사
        main_path = project_root / "main.py"
        with open(main_path, 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        # 필수 import 확인
        required_imports = [
            "from fastapi import FastAPI",
            "from fastapi.middleware.cors import CORSMiddleware",
            "from fastapi.exceptions import RequestValidationError"
        ]
        
        for required_import in required_imports:
            assert required_import in main_content, f"main.py에 {required_import}가 없습니다"
    
    def test_fastapi_app_structure(self):
        """FastAPI 앱 구조가 올바른지 테스트"""
        main_path = project_root / "main.py"
        with open(main_path, 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        # FastAPI 앱 생성 확인
        assert "app = FastAPI(" in main_content, "FastAPI 앱 생성 코드가 없습니다"
        
        # 미들웨어 추가 확인
        assert "app.add_middleware" in main_content, "미들웨어 추가 코드가 없습니다"
        
        # 라우터 등록 확인
        assert "app.include_router" in main_content, "라우터 등록 코드가 없습니다"
        
        # 라이프사이클 훅 확인
        assert "@app.on_event" in main_content, "라이프사이클 훅이 없습니다"
    
    def test_config_file_exists(self):
        """설정 파일이 존재하는지 테스트"""
        config_file = project_root / "configs" / "config.json"
        assert config_file.exists(), f"설정 파일이 존재하지 않습니다: {config_file}"
    
    def test_requirements_file_exists(self):
        """requirements.txt 파일이 존재하는지 테스트"""
        requirements_file = project_root / "requirements.txt"
        assert requirements_file.exists(), f"requirements.txt 파일이 존재하지 않습니다: {requirements_file}"
    
    def test_dockerfile_exists(self):
        """Dockerfile이 존재하는지 테스트"""
        dockerfile = project_root / "Dockerfile"
        assert dockerfile.exists(), f"Dockerfile이 존재하지 않습니다: {dockerfile}"
    
    def test_jenkinsfile_exists(self):
        """Jenkinsfile이 존재하는지 테스트"""
        jenkinsfile = project_root / "jenkinsfile"
        assert jenkinsfile.exists(), f"Jenkinsfile이 존재하지 않습니다: {jenkinsfile}"


class TestDockerBuildValidation:
    """Docker 빌드 검증 테스트 클래스"""
    
    def test_dockerfile_syntax(self):
        """Dockerfile 문법이 올바른지 테스트"""
        dockerfile_path = project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 기본적인 Dockerfile 문법 검사
        assert "FROM" in content, "Dockerfile에 FROM 명령어가 없습니다"
        assert "WORKDIR" in content, "Dockerfile에 WORKDIR 명령어가 없습니다"
        assert "COPY" in content, "Dockerfile에 COPY 명령어가 없습니다"
        assert "RUN" in content, "Dockerfile에 RUN 명령어가 없습니다"
        assert "CMD" in content, "Dockerfile에 CMD 명령어가 없습니다"
    
    def test_dockerfile_python_version(self):
        """Dockerfile의 Python 버전 확인"""
        dockerfile_path = project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Python 3.11 사용 확인
        assert "python:3.11" in content, "Dockerfile에서 Python 3.11을 사용하지 않습니다"
    
    def test_dockerfile_expose_port(self):
        """Dockerfile의 포트 노출 확인"""
        dockerfile_path = project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "EXPOSE" in content, "Dockerfile에서 포트를 노출하지 않습니다"
        assert "8000" in content, "Dockerfile에서 8000 포트를 노출하지 않습니다"
    
    def test_requirements_installable(self):
        """requirements.txt의 패키지들이 설치 가능한지 테스트"""
        requirements_file = project_root / "requirements.txt"
        
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = f.readlines()
        
        # 빈 줄과 주석 제거
        packages = [line.strip() for line in requirements if line.strip() and not line.strip().startswith('#')]
        
        assert len(packages) > 0, "설치할 패키지가 없습니다"
        
        # 각 패키지의 형식 검사
        for package in packages:
            assert '==' in package or '>=' in package or '<=' in package, f"패키지 버전이 명시되지 않았습니다: {package}"
    
    def test_dockerfile_requirements_consistency(self):
        """Dockerfile과 requirements.txt의 일관성 테스트"""
        dockerfile_path = project_root / "Dockerfile"
        requirements_path = project_root / "requirements.txt"
        
        # Dockerfile에서 requirements.txt를 사용하는지 확인
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            dockerfile_content = f.read()
        
        assert "requirements.txt" in dockerfile_content, "Dockerfile에서 requirements.txt를 사용하지 않습니다"
        assert "pip install -r requirements.txt" in dockerfile_content, "Dockerfile에서 requirements.txt 설치 명령이 없습니다"


class TestJenkinsPipelineValidation:
    """Jenkins 파이프라인 검증 테스트 클래스"""
    
    def test_jenkinsfile_syntax(self):
        """Jenkinsfile 문법이 올바른지 테스트"""
        jenkinsfile_path = project_root / "jenkinsfile"
        
        with open(jenkinsfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 기본적인 Jenkins 파이프라인 구조 확인
        assert "pipeline" in content, "Jenkinsfile에 pipeline 블록이 없습니다"
        assert "agent" in content, "Jenkinsfile에 agent 블록이 없습니다"
        assert "stages" in content, "Jenkinsfile에 stages 블록이 없습니다"
        assert "stage" in content, "Jenkinsfile에 stage 블록이 없습니다"
    
    def test_jenkinsfile_test_stage(self):
        """Jenkinsfile에 테스트 단계가 있는지 확인"""
        jenkinsfile_path = project_root / "jenkinsfile"
        
        with open(jenkinsfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 테스트 관련 단계 확인
        assert "Test" in content or "test" in content, "Jenkinsfile에 테스트 단계가 없습니다"
        assert "pytest" in content, "Jenkinsfile에 pytest 실행 코드가 없습니다"
    
    def test_jenkinsfile_docker_build(self):
        """Jenkinsfile에 Docker 빌드 단계가 있는지 확인"""
        jenkinsfile_path = project_root / "jenkinsfile"
        
        with open(jenkinsfile_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Docker 빌드 관련 단계 확인
        assert "buildah" in content or "docker" in content, "Jenkinsfile에 Docker 빌드 단계가 없습니다"
        assert "Dockerfile" in content, "Jenkinsfile에 Dockerfile 참조가 없습니다"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])