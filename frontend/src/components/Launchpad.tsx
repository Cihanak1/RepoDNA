import { FolderOpen, Github, Network } from 'lucide-react';

interface Props {
  workspace: string;
  onWorkspace: () => void;
  onBrowse: () => void;
  onGithub: () => void;
  onDemo: () => void;
  scanning: boolean;
}

export function Launchpad({ workspace, onWorkspace, onBrowse, onGithub, onDemo, scanning }: Props) {
  return <div className="launchpad" data-testid="welcome-launchpad">
    <div className="launchpad-inner">
      <div className="launchpad-intro">
        <span className="text-muted text-sm">Repository intelligence workstation</span>
        <h2>Understand the structure.<br />Find what needs attention.</h2>
        <p>Trace module dependencies, investigate coupling and review architectural findings with the evidence behind each one. Choose a repository to begin.</p>
      </div>
      <div className="launchpad-options">
        <article>
          <FolderOpen aria-hidden="true" className="text-accent" size={22} />
          <h3>Open a local repository</h3>
          <p>Analyze a directory on this machine. Files are read only when you start a scan.</p>
          {workspace && <button disabled={scanning} className="primary-action" data-testid="launchpad-scan-workspace-btn" onClick={onWorkspace}>Analyze Current Workspace</button>}
          <button disabled={scanning} onClick={onBrowse}>Browse Other Folder…</button>
          {workspace && <p className="font-mono text-xs break-all" title={workspace}>{workspace}</p>}
        </article>
        <article>
          <Github aria-hidden="true" className="text-muted" size={22} />
          <h3>Inspect a GitHub repository</h3>
          <p>Use a public HTTPS URL. The temporary clone is removed after analysis.</p>
          <button disabled={scanning} onClick={onGithub}>Enter GitHub HTTPS URL</button>
        </article>
        <article>
          <Network aria-hidden="true" className="text-muted" size={22} />
          <h3>Explore the sample</h3>
          <p>A small, labeled dataset with a dependency cycle and multiple languages.</p>
          <button disabled={scanning} data-testid="launchpad-demo-btn" onClick={onDemo}>Load Labeled Demo Mode</button>
        </article>
      </div>
      <div className="launchpad-foot"><span>Read-only analysis. Repository code never executes.</span><span>Coverage limits stay visible in every report.</span><span><kbd>Ctrl K</kbd> to search commands</span></div>
    </div>
  </div>;
}
