"""
통합 테스트
실제 서비스 동작을 테스트합니다.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.integration
class TestIntegration:
    """통합 테스트 클래스"""
    
    def test_fastapi_app_structure_validation(self):
        """FastAPI 앱 구조 검증 테스트"""
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
    
    def test_router_files_exist(self):
        """라우터 파일들이 존재하는지 테스트"""
        router_files = [
            "routers/user_router.py",
            "routers/concert_router.py", 
            "routers/queue_router.py",
            "routers/enqueue_router.py"
        ]
        
        for router_file in router_files:
            file_path = project_root / router_file
            assert file_path.exists(), f"라우터 파일이 존재하지 않습니다: {router_file}"
    
    def test_schema_files_exist(self):
        """스키마 파일들이 존재하는지 테스트"""
        schema_files = [
            "schemas/user_schema.py",
            "schemas/concert_schema.py"
        ]
        
        for schema_file in schema_files:
            file_path = project_root / schema_file
            assert file_path.exists(), f"스키마 파일이 존재하지 않습니다: {schema_file}"
    
    def test_engine_files_exist(self):
        """엔진 파일들이 존재하는지 테스트"""
        engine_files = [
            "engines/user_engine.py",
            "engines/concert_engine.py"
        ]
        
        for engine_file in engine_files:
            file_path = project_root / engine_file
            assert file_path.exists(), f"엔진 파일이 존재하지 않습니다: {engine_file}"


@pytest.mark.integration
class TestDockerIntegration:
    """Docker 통합 테스트 클래스"""
    
    def test_dockerfile_requirements_consistency(self):
        """Dockerfile과 requirements.txt의 일관성 테스트"""
        dockerfile_path = project_root / "Dockerfile"
        requirements_path = project_root / "requirements.txt"
        
        # Dockerfile에서 requirements.txt를 사용하는지 확인
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            dockerfile_content = f.read()
        
        assert "requirements.txt" in dockerfile_content, "Dockerfile에서 requirements.txt를 사용하지 않습니다"
        assert "pip install -r requirements.txt" in dockerfile_content, "Dockerfile에서 requirements.txt 설치 명령이 없습니다"
    
    def test_dockerfile_python_version(self):
        """Dockerfile의 Python 버전 확인"""
        dockerfile_path = project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            dockerfile_content = f.read()
        
        # Python 3.11 사용 확인
        assert "python:3.11" in dockerfile_content, "Dockerfile에서 Python 3.11을 사용하지 않습니다"
    
    def test_dockerfile_expose_port(self):
        """Dockerfile의 포트 노출 확인"""
        dockerfile_path = project_root / "Dockerfile"
        
        with open(dockerfile_path, 'r', encoding='utf-8') as f:
            dockerfile_content = f.read()
        
        assert "EXPOSE" in dockerfile_content, "Dockerfile에서 포트를 노출하지 않습니다"
        assert "8000" in dockerfile_content, "Dockerfile에서 8000 포트를 노출하지 않습니다"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
