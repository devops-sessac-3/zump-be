#!/bin/bash

# 테스트 실행 스크립트
# 사용법: ./run_tests.sh [test_type]
# test_type: unit, integration, all (기본값: all)

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 함수 정의
print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 테스트 타입 설정
TEST_TYPE=${1:-all}

print_info "테스트 실행을 시작합니다..."
print_info "테스트 타입: $TEST_TYPE"

# 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
    print_info "가상환경을 생성합니다..."
    python3.11 -m venv venv || python3 -m venv venv
fi

# 가상환경 활성화
print_info "가상환경을 활성화합니다..."
source venv/bin/activate

# 의존성 설치
print_info "의존성을 설치합니다..."
pip install --upgrade pip
pip install -r requirements.txt

# 테스트 실행
case $TEST_TYPE in
    "unit")
        print_info "단위 테스트를 실행합니다..."
        pytest tests/test_build_validation.py -v
        ;;
    "integration")
        print_info "통합 테스트를 실행합니다..."
        pytest tests/ -m integration -v
        ;;
    "all")
        print_info "모든 테스트를 실행합니다..."
        pytest tests/ -v
        ;;
    *)
        print_error "잘못된 테스트 타입입니다. 사용법: ./run_tests.sh [unit|integration|all]"
        exit 1
        ;;
esac

# 테스트 결과 확인
if [ $? -eq 0 ]; then
    print_success "모든 테스트가 성공적으로 완료되었습니다!"
else
    print_error "테스트 실행 중 오류가 발생했습니다."
    exit 1
fi

print_info "테스트 실행이 완료되었습니다."
