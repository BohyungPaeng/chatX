"use client";

import React, { useState } from 'react';
import { User } from 'lucide-react';

interface PDFGreetingMessageProps {
  fileName: string;
  iconSrc?: string;
  onMasterSettingSubmit?: (prompt: string) => void;
}

interface MasterSettingCardProps {
  onSubmit?: (prompt: string) => void;
  onClose?: () => void;
  className?: string;
}

// 마스터 설정 카드 컴포넌트 - 더 깔끔하게
function MasterSettingCard({ onSubmit, onClose, className = "" }: MasterSettingCardProps) {
  const [role, setRole] = useState('');
  const [expertise, setExpertise] = useState('');
  const [task, setTask] = useState('');
  const [guidelines, setGuidelines] = useState('');
  const [tone, setTone] = useState('친근하고 전문적');

  const handleSubmit = () => {
    const prompt = `다음과 같이 행동해주세요:

${role}로서 ${expertise} 전문 지식을 활용하여,
${task}을(를) 수행해주세요.

가이드라인: ${guidelines}
톤앤매너: ${tone}

잘 부탁드립니다!`;
    
    onSubmit?.(prompt);
    onClose?.();
  };

  return (
    <div className={className}>
      {/* 헤더 */}
      <div className="text-center mb-6">
        <h3 className="text-lg font-bold text-gray-800 dark:text-white mb-2">
          AI 어시스턴트 전용 마스터 설정
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          아래 양식을 작성하여 맞춤형 어시스턴트를 설정하세요.
        </p>
      </div>

      {/* 폼 필드들 */}
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            역할 설정 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder="예: 법무 전문가"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            전문 분야 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            placeholder="예: 계약서 분석"
            value={expertise}
            onChange={(e) => setExpertise(e.target.value)}
            className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            구체적 업무 또는 목표 <span className="text-red-500">*</span>
          </label>
          <textarea
            placeholder="예: 위험 조항 분석 및 개선 방안 제시"
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={3}
            className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            가이드라인 또는 제한사항
          </label>
          <textarea
            placeholder="예: 법적 근거 명시"
            value={guidelines}
            onChange={(e) => setGuidelines(e.target.value)}
            rows={2}
            className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            톤앤매너
          </label>
          <select
            value={tone}
            onChange={(e) => setTone(e.target.value)}
            className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="친근하고 전문적">친근하고 전문적</option>
            <option value="격식있고 공식적">격식있고 공식적</option>
            <option value="간결하고 명확">간결하고 명확</option>
            <option value="상세하고 교육적">상세하고 교육적</option>
          </select>
        </div>
      </div>

      {/* 필수 필드 안내 */}
      <p className="text-sm text-gray-500 dark:text-gray-400 mt-4 mb-4">
        * 필수 입력 항목
      </p>

      {/* 버튼들 */}
      <div className="flex gap-3">
        <button
          onClick={onClose}
          className="flex-1 bg-gray-200 hover:bg-gray-300 dark:bg-gray-600 dark:hover:bg-gray-500 text-gray-800 dark:text-white font-medium py-3 px-4 rounded-lg transition-colors duration-200"
        >
          취소
        </button>
        <button
          onClick={handleSubmit}
          disabled={!role || !expertise || !task}
          className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-3 px-4 rounded-lg transition-colors duration-200 disabled:cursor-not-allowed"
        >
          설정 완료
        </button>
      </div>
    </div>
  );
}

export function PDFGreetingMessage({ fileName, iconSrc, onMasterSettingSubmit }: PDFGreetingMessageProps) {
  const cleanFileName = fileName?.replace(/\.[^/.]+$/, '') || 'PDF 문서';
  const [showMasterSetting, setShowMasterSetting] = useState(false);
  const [skipMasterSetting, setSkipMasterSetting] = useState(false);

  const handleMasterSettingSubmit = (prompt: string) => {
    onMasterSettingSubmit?.(prompt);
    setShowMasterSetting(false);
  };

  const handleSkipMasterSetting = () => {
    setSkipMasterSetting(true);
    setShowMasterSetting(false);
    console.log("마스터 설정을 건너뛰었습니다.");
  };

  // 자동 표시 제거 - 버튼 클릭으로만 표시
  // React.useEffect(() => {
  //   const timer = setTimeout(() => {
  //     setShowMasterSetting(true);
  //   }, 1500);
  //   return () => clearTimeout(timer);
  // }, []);
  
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
        {/* 256x256 아이콘 (좌측) - 디버깅 정보 제거 */}
        {iconSrc ? (
          <div className="flex-shrink-0">
            <img 
              src={iconSrc} 
              alt="AI Assistant Icon"
              className="w-64 h-64 rounded-2xl shadow-xl object-cover border-4 border-blue-100 dark:border-blue-800"
              onError={(e) => console.error('Icon load error:', e)}
              onLoad={() => console.log('Icon loaded successfully:', iconSrc?.substring(0, 50))}
            />
          </div>
        ) : (
          <div className="w-64 h-64 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-xl flex-shrink-0">
            <span className="text-8xl">🤖</span>
          </div>
        )}
        
        {/* 말풍선 (우측) - 더 선명하고 대비 강화 */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 shadow-xl border-2 border-gray-300 dark:border-gray-600 relative max-w-md min-w-[320px] w-full sm:w-1/2">
          {/* 말풍선 꼬리 - 더 선명하게 */}
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
          본 대화 세션의 목표를 공유해주시면 선생님을 더 잘 도와드릴 수 있습니다. 😊
        </p>
        
        {/* 버튼들과 유저 아바타 */}
        <div className="flex items-center gap-3 ml-4">
          {/* 마스터 설정 관련 버튼들 */}
          <div className="flex gap-2">
            <button
              onClick={handleSkipMasterSetting}
              className={`px-6 py-3 font-semibold rounded-lg transition-colors duration-200 whitespace-nowrap shadow-lg ${
                skipMasterSetting 
                  ? 'bg-white border-4 border-black text-black' 
                  : 'bg-gray-200 hover:bg-gray-300 dark:bg-gray-600 dark:hover:bg-gray-500 text-gray-800 dark:text-white'
              }`}
            >
              마스터 설정 안하기
            </button>
            
            <button
              onClick={() => {
                setShowMasterSetting(!showMasterSetting);
                if (skipMasterSetting) setSkipMasterSetting(false); // 마스터 설정 클릭시 안하기 해제
              }}
              className={`px-6 py-3 font-semibold rounded-lg transition-colors duration-200 whitespace-nowrap shadow-lg ${
                showMasterSetting 
                  ? 'bg-blue-700 text-white' 
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {showMasterSetting ? '마스터 설정 닫기' : '대화 세션 마스터 설정'}
            </button>
          </div>
          
          {/* 유저 아바타 - chat-message.tsx와 완전 동일 */}
          <div className="h-10 w-10 rounded-lg bg-orange-500 flex items-center justify-center flex-shrink-0">
            <User className="h-6 w-6 text-white" />
          </div>
        </div>
      </div>

      {/* 마스터 설정 카드 - 우측 하단에 위치 */}
      {showMasterSetting && (
        <div className="flex justify-end mt-6">
          <div className="w-96 bg-white dark:bg-gray-800 rounded-xl shadow-xl border-2 border-gray-300 dark:border-gray-600 p-6">
            <MasterSettingCard 
              onSubmit={handleMasterSettingSubmit}
              onClose={() => setShowMasterSetting(false)}
              className="w-full"
            />
          </div>
        </div>
      )}
    </div>
  );
}