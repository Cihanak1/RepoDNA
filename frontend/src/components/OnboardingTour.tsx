import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, ArrowRight, Check, Compass, Sparkles, X } from 'lucide-react';

interface OnboardingTourProps {
  isOpen: boolean;
  onClose: () => void;
  onTryDemo: () => void;
}

export const OnboardingTour: React.FC<OnboardingTourProps> = ({
  isOpen,
  onClose,
  onTryDemo,
}) => {
  const { t } = useTranslation();
  const [step, setStep] = useState(1);
  const totalSteps = 4;
  const dialogRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      setStep(1);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowRight') {
        setStep((s) => (s < totalSteps ? s + 1 : s));
      } else if (e.key === 'ArrowLeft') {
        setStep((s) => (s > 1 ? s - 1 : s));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleNext = () => {
    if (step < totalSteps) {
      setStep((s) => s + 1);
    } else {
      onClose();
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep((s) => s - 1);
    }
  };

  const stepsData = [
    {
      title: t('onboarding.step1Title'),
      desc: t('onboarding.step1Desc'),
      action: (
        <button
          type="button"
          data-testid="onboarding-demo-btn"
          onClick={() => {
            onClose();
            onTryDemo();
          }}
          className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-accent-solid text-white text-xs font-semibold hover:opacity-90 cursor-pointer shadow-sm transition"
        >
          <Sparkles className="w-4 h-4" aria-hidden="true" />
          {t('onboarding.tryDemo')}
        </button>
      ),
    },
    {
      title: t('onboarding.step2Title'),
      desc: t('onboarding.step2Desc'),
      action: null,
    },
    {
      title: t('onboarding.step3Title'),
      desc: t('onboarding.step3Desc'),
      action: null,
    },
    {
      title: t('onboarding.step4Title'),
      desc: t('onboarding.step4Desc'),
      action: null,
    },
  ];

  const currentStepData = stepsData[step - 1];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
      data-testid="onboarding-tour-modal"
      className="fixed bottom-6 right-6 z-50 max-w-sm w-full bg-panel border border-accent/40 rounded-xl shadow-2xl p-4 text-ink flex flex-col gap-3 animate-in fade-in slide-in-from-bottom-2 duration-150"
      ref={dialogRef}
    >
      <div className="flex items-center justify-between border-b border-line pb-2">
        <div className="flex items-center gap-2 text-accent font-semibold text-xs tracking-wide">
          <Compass className="w-4 h-4" aria-hidden="true" />
          <span id="onboarding-title">{t('onboarding.title')}</span>
        </div>
        <div className="flex items-center gap-2">
          <span data-testid="onboarding-step-indicator" className="text-[11px] font-mono text-muted">
            {t('onboarding.step', { current: step, total: totalSteps })}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('common.close')}
            className="p-1 rounded hover:bg-raised text-muted hover:text-ink cursor-pointer"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="space-y-1.5 py-1">
        <h3 className="text-sm font-bold text-ink m-0">{currentStepData.title}</h3>
        <p className="text-xs text-muted leading-relaxed m-0">{currentStepData.desc}</p>
        {currentStepData.action}
      </div>

      {/* Progress Dots & Navigation */}
      <div className="flex items-center justify-between pt-2 border-t border-line">
        <div className="flex items-center gap-1.5" aria-hidden="true">
          {[1, 2, 3, 4].map((dot) => (
            <span
              key={dot}
              className={`h-1.5 rounded-full transition-all ${
                dot === step ? 'w-5 bg-accent' : 'w-1.5 bg-line'
              }`}
            />
          ))}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="onboarding-skip-btn"
            onClick={onClose}
            className="text-xs text-muted hover:text-ink px-2 py-1 cursor-pointer"
          >
            {t('onboarding.skip')}
          </button>
          {step > 1 && (
            <button
              type="button"
              onClick={handleBack}
              aria-label={t('onboarding.back')}
              className="p-1.5 rounded bg-raised hover:bg-line text-ink cursor-pointer text-xs"
            >
              <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          )}
          <button
            type="button"
            data-testid="onboarding-next-btn"
            onClick={handleNext}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-accent-solid text-white text-xs font-medium hover:opacity-90 cursor-pointer shadow-sm"
          >
            <span>{step === totalSteps ? t('onboarding.finish') : t('onboarding.next')}</span>
            {step === totalSteps ? (
              <Check className="w-3.5 h-3.5" aria-hidden="true" />
            ) : (
              <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
