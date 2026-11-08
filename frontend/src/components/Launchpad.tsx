import { useTranslation } from 'react-i18next';
import { FolderOpen, Github, Sparkles } from 'lucide-react';

interface Props {
  workspace: string;
  onWorkspace: () => void;
  onBrowse: () => void;
  onGithub: () => void;
  onDemo: () => void;
  scanning: boolean;
}

export function Launchpad({ workspace, onWorkspace, onBrowse, onGithub, onDemo, scanning }: Props) {
  const { t } = useTranslation();

  return (
    <div className="launchpad" data-testid="welcome-launchpad">
      <div className="launchpad-inner">
        <div className="launchpad-intro">
          <span className="text-muted text-xs uppercase tracking-wider font-semibold">
            {t('header.subtitle')}
          </span>
          <h2>{t('launchpad.headline')}</h2>
          <p>{t('launchpad.subline')}</p>
        </div>

        <div className="launchpad-options">
          {/* 1. Local Workspace */}
          <article>
            <FolderOpen aria-hidden="true" className="text-accent" size={22} />
            <h3>{t('launchpad.localTitle')}</h3>
            <p>{t('launchpad.localDesc')}</p>
            {workspace && (
              <button
                type="button"
                disabled={scanning}
                className="primary-action"
                data-testid="launchpad-scan-workspace-btn"
                onClick={onWorkspace}
              >
                {t('launchpad.analyzeWorkspace')}
              </button>
            )}
            <button
              type="button"
              disabled={scanning}
              onClick={onBrowse}
            >
              {t('launchpad.browseFolder')}
            </button>
            {workspace && (
              <p className="font-mono text-[11px] text-muted truncate mt-2" title={workspace}>
                {workspace}
              </p>
            )}
          </article>

          {/* 2. GitHub */}
          <article>
            <Github aria-hidden="true" className="text-muted" size={22} />
            <h3>{t('launchpad.githubTitle')}</h3>
            <p>{t('launchpad.githubDesc')}</p>
            <button
              type="button"
              disabled={scanning}
              onClick={onGithub}
            >
              {t('launchpad.githubBtn')}
            </button>
          </article>

          {/* 3. Demo Showcase */}
          <article>
            <Sparkles aria-hidden="true" className="text-accent" size={22} />
            <h3>{t('launchpad.demoTitle')}</h3>
            <p>{t('launchpad.demoDesc')}</p>
            <button
              type="button"
              disabled={scanning}
              data-testid="launchpad-demo-btn"
              onClick={onDemo}
              className="border-accent/40 hover:border-accent text-accent font-semibold"
            >
              {t('launchpad.demoBtn')}
            </button>
          </article>
        </div>

        <div className="launchpad-foot">
          <span>{t('launchpad.footSecurity')}</span>
          <span>{t('launchpad.footCoverage')}</span>
          <span>
            <kbd className="px-1.5 py-0.5 rounded bg-raised border border-line text-[11px] font-mono">
              Ctrl K
            </kbd>{' '}
            {t('launchpad.footShortcuts')}
          </span>
        </div>
      </div>
    </div>
  );
}
