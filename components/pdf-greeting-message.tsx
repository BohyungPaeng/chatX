"use client";

import React, { useState } from 'react';
import { User } from 'lucide-react';

interface PDFGreetingMessageProps {
  fileName: string;
  iconSrc?: string;
  onMasterSettingSubmit?: (prompt: string) => void;
}

interface MasterSettingCardProps {
  onSystemSubmit?: (systemPrompt: string) => void;  // 🆕 시스템 프롬프트 전용
  onQuestionSubmit?: (question: string) => void;    // 🆕 추천 질문 전용
  onClose?: () => void;
  className?: string;
}

// 마스터 설정 카드 컴포넌트 - 두 개 함수로 분리!
function MasterSettingCard({ onSystemSubmit, onQuestionSubmit, onClose, className = "" }: MasterSettingCardProps) {
  const [role, setRole] = useState('법무 전문가');
  const [expertise, setExpertise] = useState('계약서 분석');
  const [task, setTask] = useState('위험 조항 분석 및 개선 방안 제시');
  const [guidelines, setGuidelines] = useState('법적 근거 명시');
  const [tone, setTone] = useState('친근하고 전문적');
  const [isCompleted, setIsCompleted] = useState(false);

  const handleSubmit = () => {
    const prompt = `다음과 같이 행동해주세요:

${role}로서 ${expertise} 전문 지식을 활용하여,
${task}을(를) 수행해주세요.

가이드라인: ${guidelines}
톤앤매너: ${tone}

잘 부탁드립니다!`;
    
    // 🎯 시스템 프롬프트는 별도 함수로!
    onSystemSubmit?.(prompt);
    setIsCompleted(true);
    console.log("✅ 마스터 설정 완료 - 시스템 프롬프트:", prompt);
  };

  return (
    <div className={className}>
      {/* 헤더 - 스크린샷처럼 자연스럽게 */}
      <div className="text-center mb-8">
        <h3 className="text-xl font-bold text-gray-800 dark:text-white mb-3">
          AI 어시스턴트 전용 마스터 설정
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          아래 양식을 작성하여 맞춤형 어시스턴트를 설정하세요.
        </p>
      </div>

      {/* 폼 필드들 - 스크린샷처럼 깔끔하게 */}
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2" style={{color: isCompleted ? '#dc2626' : '#6b7280'}}>
            역할 설정 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder="예: 법무 전문가"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            style={{color: isCompleted ? '#dc2626' : 'inherit'}}
            className="w-full p-3 border-0 border-b-2 border-gray-200 dark:border-gray-600 bg-transparent text-gray-900 dark:text-white focus:border-blue-500 focus:outline-none transition-all duration-200"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2" style={{color: isCompleted ? '#dc2626' : '#6b7280'}}>
            전문 분야 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder="예: 계약서 분석"
            value={expertise}
            onChange={(e) => setExpertise(e.target.value)}
            style={{color: isCompleted ? '#dc2626' : 'inherit'}}
            className="w-full p-3 border-0 border-b-2 border-gray-200 dark:border-gray-600 bg-transparent text-gray-900 dark:text-white focus:border-blue-500 focus:outline-none transition-all duration-200"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2" style={{color: isCompleted ? '#dc2626' : '#6b7280'}}>
            구체적 업무 또는 목표 <span className="text-red-500">*</span>
          </label>
          <textarea
            placeholder="예: 위험 조항 분석 및 개선 방안 제시"
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={3}
            style={{color: isCompleted ? '#dc2626' : 'inherit'}}
            className="w-full p-3 border-0 border-b-2 border-gray-200 dark:border-gray-600 bg-transparent text-gray-900 dark:text-white focus:border-blue-500 focus:outline-none transition-all duration-200 resize-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2" style={{color: isCompleted ? '#dc2626' : '#6b7280'}}>
            가이드라인 또는 제한사항
          </label>
          <input
            type="text"
            placeholder="예: 법적 근거 명시"
            value={guidelines}
            onChange={(e) => setGuidelines(e.target.value)}
            style={{color: isCompleted ? '#dc2626' : 'inherit'}}
            className="w-full p-3 border-0 border-b-2 border-gray-200 dark:border-gray-600 bg-transparent text-gray-900 dark:text-white focus:border-blue-500 focus:outline-none transition-all duration-200"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2" style={{color: isCompleted ? '#dc2626' : '#6b7280'}}>
            톤앤매너
          </label>
          <select
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            style={{color: isCompleted ? '#dc2626' : 'inherit'}}
            className="w-full p-3 border-0 border-b-2 border-gray-200 dark:border-gray-600 bg-transparent text-gray-900 dark:text-white focus:border-blue-500 focus:outline-none transition-all duration-200"
          >
            <option value="친근하고 전문적">친근하고 전문적</option>
            <option value="격식있고 공식적">격식있고 공식적</option>
            <option value="간결하고 명확">간결하고 명확</option>
            <option value="상세하고 교육적">상세하고 교육적</option>
          </select>
        </div>
      </div>

      {/* 필수 필드 안내 */}
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-6 mb-6">
        * 필수 입력 항목
      </p>

      {/* 버튼들 - 자연스럽게 */}
      <div className="flex gap-3">
        <button
          onClick={onClose}
          className="flex-1 py-3 px-4 font-medium text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white transition-colors duration-200"
        >
          취소
        </button>
        <button
          onClick={handleSubmit}
          disabled={!role || !expertise || !task}
          className={`flex-1 py-3 px-4 font-semibold rounded-lg transition-colors duration-200 ${
            isCompleted 
              ? 'bg-red-600 text-white' 
              : 'bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white disabled:cursor-not-allowed'
          }`}
        >
          {isCompleted ? '설정 완료됨 ✓' : '설정 완료'}
        </button>
      </div>

      {/* 🎯 추천 질문들 - 완전히 다른 함수로! */}
      {isCompleted && (
        <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-600">
          <h4 className="text-md font-semibold text-gray-800 dark:text-white mb-4">
            추천 질문
          </h4>
          <div className="space-y-3">
            <button
              onClick={() => onQuestionSubmit?.("이 문서의 주요 내용을 요약해주세요.")}
              className="w-full p-3 text-left bg-orange-50 hover:bg-orange-100 dark:bg-orange-900/20 dark:hover:bg-orange-900/40 text-orange-800 dark:text-orange-200 rounded-lg transition-colors duration-200 border border-orange-200 dark:border-orange-800"
            >
              💡 이 문서의 주요 내용을 요약해주세요.
            </button>
            <button
              onClick={() => onQuestionSubmit?.("중요한 조항이나 주의사항이 있나요?")}
              className="w-full p-3 text-left bg-orange-50 hover:bg-orange-100 dark:bg-orange-900/20 dark:hover:bg-orange-900/40 text-orange-800 dark:text-orange-200 rounded-lg transition-colors duration-200 border border-orange-200 dark:border-orange-800"
            >
              ⚠️ 중요한 조항이나 주의사항이 있나요?
            </button>
            <button
              onClick={() => onQuestionSubmit?.("이 계약에서 우리 회사에게 불리한 부분은 무엇인가요?")}
              className="w-full p-3 text-left bg-orange-50 hover:bg-orange-100 dark:bg-orange-900/20 dark:hover:bg-orange-900/40 text-orange-800 dark:text-orange-200 rounded-lg transition-colors duration-200 border border-orange-200 dark:border-orange-800"
            >
              🔍 이 계약에서 우리 회사에게 불리한 부분은 무엇인가요?
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export function PDFGreetingMessage({ fileName, iconSrc, onMasterSettingSubmit }: PDFGreetingMessageProps) {
  const cleanFileName = fileName?.replace(/\.[^/.]+$/, '') || 'PDF 문서';
  const [showMasterSetting, setShowMasterSetting] = useState(false);
  const [skipMasterSetting, setSkipMasterSetting] = useState(false);
  const [masterSettingCompleted, setMasterSettingCompleted] = useState(false);

  // 🎯 시스템 프롬프트 처리 - SYSTEM_PROMPT: 붙여서 전달
  const handleSystemPromptSubmit = (systemPrompt: string) => {
    if (onMasterSettingSubmit) {
      onMasterSettingSubmit(`SYSTEM_PROMPT:${systemPrompt}`);
    }
    setMasterSettingCompleted(true);
    console.log("📋 시스템 프롬프트 설정:", systemPrompt);
  };

  // 🎯 추천 질문 처리 - 그냥 질문만 전달
  const handleQuestionSubmit = (question: string) => {
    if (onMasterSettingSubmit) {
      onMasterSettingSubmit(question);  // 플래그 없이 바로!
    }
    console.log("💡 추천 질문 선택:", question);
  };

  const handleSkipMasterSetting = () => {
    setSkipMasterSetting(true);
    setShowMasterSetting(false);
    // 🔧 버그 수정: 건너뛰기는 완료와 다름! 
    console.log("마스터 설정을 건너뛰었습니다.");
  };
  
  return (
    <div className="space-y-4">
      {/* 분석 완료 안내 */}
      <p className="text-gray-800 dark:text-white">
        <strong>{cleanFileName}</strong> 분석이 완료되었습니다.
      </p>
      
      {/* 구분선 */}
      <hr className="border-gray-200 dark:border-gray-600 my-4" />
      
      {/* 큰 아이콘과 인사 (좌측 정렬) */}
      <div className="flex items-start gap-4 py-4">
        {/* 256x256 아이콘 (좌측) */}
        {iconSrc ? (
          <div className="flex-shrink-0">
            <img 
              src={iconSrc} 
              alt="AI Assistant Icon"
              className="w-64 h-64 rounded-2xl shadow-xl object-cover border-4 border-blue-100 dark:border-blue-800"
              onError={(e) => console.error('Icon load error:', e)}
              onLoad={() => console.log('Icon loaded successfully')}
            />
          </div>
        ) : (
          <div className="w-64 h-64 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-xl flex-shrink-0">
            <span className="text-8xl">🤖</span>
          </div>
        )}
        
        {/* 말풍선 (우측) */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-xl border-2 border-gray-300 dark:border-gray-600 relative max-w-md min-w-[320px] w-full sm:w-1/2">
          {/* 말풍선 꼬리 */}
          <div className="absolute left-0 top-6 w-0 h-0 border-t-[12px] border-t-transparent border-b-[12px] border-b-transparent border-r-[16px] border-r-white dark:border-r-gray-800 -ml-4"></div>
          
          <div className="space-y-3">
            <p className="text-gray-900 dark:text-white font-medium text-lg">
              안녕하세요! 👋
            </p>
            <p className="text-lg text-gray-700 dark:text-gray-300">
              저는 <span className="font-semibold text-blue-600 dark:text-blue-400">{cleanFileName}</span> 전용 AI 어시스턴트입니다.
            </p>
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed font-medium">
              업로드하신 문서를 기반으로 더 정확하고 맞춤형 답변을 제공해드리겠습니다.
            </p>
          </div>
        </div>
      </div>

      {/* 마지막 안내 문구 + 버튼들 + 유저 아바타 */}
      <div className="flex items-center justify-between mt-6">
        <p className="text-gray-800 dark:text-gray-200 font-medium flex-1">
          {/* 동적 메시지 유지 */}
          {masterSettingCompleted 
            ? "마스터 설정이 완료되었습니다! 이제 문서에 대해 질문해보세요. 😊"
            : "본 대화 세션의 목표를 공유해주시면 선생님을 더 잘 도와드릴 수 있습니다. 😊"
          }
        </p>
        
        {/* 버튼들과 유저 아바타 */}
        <div className="flex items-center gap-3 ml-4">
          {/* 마스터 설정 관련 버튼들 - 버그 수정: 건너뛰기와 완료 구분 */}
          <div className="flex gap-2">
            <button
              onClick={handleSkipMasterSetting}
              className={`px-6 py-3 font-semibold rounded-lg transition-all duration-200 whitespace-nowrap shadow-lg ${
                skipMasterSetting 
                  ? 'border-4 border-black text-black bg-transparent' 
                  : 'bg-gray-200 hover:bg-gray-300 dark:bg-gray-600 dark:hover:bg-gray-500 text-gray-800 dark:text-white'
              }`}
            >
              마스터 설정 안하기
            </button>
            
            <button
              onClick={() => {
                setShowMasterSetting(!showMasterSetting);
                if (skipMasterSetting) setSkipMasterSetting(false);
              }}
              className={`px-6 py-3 font-semibold rounded-lg transition-colors duration-200 whitespace-nowrap shadow-lg ${
                showMasterSetting 
                  ? 'bg-blue-700 text-white' 
                  : masterSettingCompleted
                  ? 'bg-red-600 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {showMasterSetting ? '마스터 설정 닫기' : 
               masterSettingCompleted ? '마스터 설정됨 ✓' : '대화 세션 마스터 설정'}
            </button>
          </div>
          
          {/* 유저 아바타 */}
          <div className="h-10 w-10 rounded-lg bg-orange-500 flex items-center justify-center flex-shrink-0">
            <User className="h-6 w-6 text-white" />
          </div>
        </div>
      </div>

      {/* 🎯 마스터 설정 카드 - 두 개 함수로 분리해서 전달! */}
      {showMasterSetting && (
        <div className="flex justify-end mt-6">
          <div className="w-96 bg-white dark:bg-gray-800 rounded-xl shadow-xl p-6">
            <MasterSettingCard 
              onSystemSubmit={handleSystemPromptSubmit}    // 시스템 프롬프트용
              onQuestionSubmit={handleQuestionSubmit}      // 추천 질문용
              onClose={() => setShowMasterSetting(false)}
              className="w-full"
            />
          </div>
        </div>
      )}
    </div>
  );
}