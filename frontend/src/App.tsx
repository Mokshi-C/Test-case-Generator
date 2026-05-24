import { FormEvent, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  CheckCircle2,
  Code2,
  Download,
  FileText,
  Moon,
  Play,
  Server,
  Sun,
  Upload,
} from 'lucide-react';
import {
  Artifact,
  AutomationFile,
  ConfigOptions,
  JobStatus,
  generateAutomation,
  generateTests,
  getConfigOptions,
  getJob,
  ingestCode,
  ingestDocuments,
} from './api';

type Theme = 'light' | 'dark';

const defaultConfig: ConfigOptions = {
  providers: [],
  languages: ['python'],
  frameworks: { python: ['pytest'] },
  output_formats: ['md'],
  defaults: {
    collection_name: 'test_collection',
    language: 'python',
    framework: 'pytest',
    output_format: 'md',
  },
};

function App() {
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem('theme') as Theme) || 'dark');
  const [config, setConfig] = useState<ConfigOptions>(defaultConfig);
  const [collection, setCollection] = useState('test_collection');
  const [serverPath, setServerPath] = useState('');
  const [sourcePath, setSourcePath] = useState('');
  const [files, setFiles] = useState<FileList | null>(null);
  const [query, setQuery] = useState('Generate comprehensive QA coverage for unit, integration, API, frontend flow, and edge-case scenarios.');
  const [outputFormat, setOutputFormat] = useState('md');
  const [language, setLanguage] = useState('python');
  const [framework, setFramework] = useState('pytest');
  const [activeJob, setActiveJob] = useState<JobStatus | null>(null);
  const [generatedContent, setGeneratedContent] = useState('');
  const [testArtifact, setTestArtifact] = useState<Artifact | null>(null);
  const [automationArtifact, setAutomationArtifact] = useState<Artifact | null>(null);
  const [automationFiles, setAutomationFiles] = useState<AutomationFile[]>([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const availableFrameworks = useMemo(() => config.frameworks[language] || [], [config, language]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    getConfigOptions()
      .then((options) => {
        setConfig(options);
        setCollection(options.defaults.collection_name || 'test_collection');
        setLanguage(options.defaults.language || 'python');
        setFramework(options.defaults.framework || 'pytest');
        setOutputFormat(options.defaults.output_format || 'md');
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!availableFrameworks.includes(framework)) {
      setFramework(availableFrameworks[0] || '');
    }
  }, [availableFrameworks, framework]);

  async function watchJob(jobId: string, success: (job: JobStatus) => void) {
    setError('');
    setNotice('Job queued');
    const timer = window.setInterval(async () => {
      try {
        const job = await getJob(jobId);
        setActiveJob(job);
        setNotice(job.message);
        if (job.state === 'completed') {
          window.clearInterval(timer);
          success(job);
        }
        if (job.state === 'failed') {
          window.clearInterval(timer);
          setError(job.error || 'Job failed');
        }
      } catch (err) {
        window.clearInterval(timer);
        setError(err instanceof Error ? err.message : 'Unable to read job status');
      }
    }, 1200);
  }

  async function submitDocuments(event: FormEvent) {
    event.preventDefault();
    const formData = new FormData();
    if (files) Array.from(files).forEach((file) => formData.append('files', file));
    if (serverPath.trim()) formData.append('path', serverPath.trim());
    formData.append('collection_name', collection);
    const response = await ingestDocuments(formData);
    watchJob(response.job_id, (job) => setNotice(`Indexed ${job.result?.count ?? 0} items`));
  }

  async function submitCode(event: FormEvent) {
    event.preventDefault();
    if (!sourcePath.trim()) {
      setError('Add a local source path or GitHub repository URL.');
      return;
    }
    const response = await ingestCode({ source_path: sourcePath.trim(), collection_name: collection });
    watchJob(response.job_id, (job) => setNotice(`Code context ready with ${job.result?.count ?? 0} indexed items`));
  }

  async function submitGenerate(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) {
      setError('Describe the coverage you want to generate.');
      return;
    }
    const response = await generateTests({
      query: query.trim(),
      collection_name: collection,
      num_retrieved: 5,
      output_format: outputFormat,
    });
    watchJob(response.job_id, (job) => {
      const result = job.result || {};
      setGeneratedContent(String(result.content || ''));
      setTestArtifact((result.artifact as Artifact) || null);
      setNotice('Test cases generated');
    });
  }

  async function submitAutomation(event: FormEvent) {
    event.preventDefault();
    if (!generatedContent && !testArtifact) {
      setError('Generate test cases before creating automation.');
      return;
    }
    const response = await generateAutomation({
      test_case_content: generatedContent || undefined,
      artifact_id: !generatedContent && testArtifact ? testArtifact.id : undefined,
      collection_name: collection,
      language,
      framework,
      num_context_docs: 5,
    });
    watchJob(response.job_id, (job) => {
      const result = job.result || {};
      setAutomationFiles((result.files as AutomationFile[]) || []);
      setAutomationArtifact((result.artifact as Artifact) || null);
      setNotice('Automation suite generated');
    });
  }

  function scrollToWorkflow() {
    document.getElementById('workflow')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950 transition-colors dark:bg-slate-950 dark:text-slate-50">
      <section className="relative overflow-hidden border-b border-slate-200 dark:border-slate-800">
        <AnimatedGrid />
        <nav className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-md bg-slate-950 text-white dark:bg-white dark:text-slate-950">
              <CheckCircle2 size={19} />
            </div>
            <span className="text-lg font-semibold tracking-normal">TestTeller</span>
          </div>
          <button
            className="icon-button"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </nav>

        <div className="relative z-10 mx-auto grid min-h-[calc(100vh-80px)] max-w-7xl content-center gap-10 px-6 py-14 lg:grid-cols-[1.05fr_0.95fr]">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.55 }}>
            <p className="mb-4 text-sm font-semibold uppercase text-cyan-700 dark:text-cyan-300">AI test generation for modern QA teams</p>
            <h1 className="max-w-4xl text-5xl font-semibold leading-tight tracking-normal md:text-7xl">TestTeller</h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600 dark:text-slate-300">
              Analyze requirements, APIs, and frontend flows to produce test cases and executable automation from one focused workspace.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <button className="primary-button" onClick={scrollToWorkflow}>
                Accelerate QA <ArrowRight size={18} />
              </button>
              <button className="secondary-button" onClick={scrollToWorkflow}>
                Open Workflow <Play size={17} />
              </button>
            </div>
          </motion.div>

          <motion.div
            className="hero-panel"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            {[
              ['Requirements', 'Document intelligence', 'Ready'],
              ['Backend APIs', 'Contract and edge coverage', 'Indexed'],
              ['Frontend flows', 'User journeys and selectors', 'Mapped'],
              ['Automation', `${language}/${framework}`, 'Generated'],
            ].map(([title, detail, status]) => (
              <div className="signal-row" key={title}>
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">{detail}</p>
                </div>
                <span>{status}</span>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      <section id="workflow" className="mx-auto max-w-7xl px-6 py-12">
        <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="text-sm font-semibold uppercase text-cyan-700 dark:text-cyan-300">Workflow</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-normal">Generate QA coverage</h2>
          </div>
          <label className="field compact">
            Collection
            <input value={collection} onChange={(event) => setCollection(event.target.value)} />
          </label>
        </div>

        {(notice || error || activeJob) && (
          <div className="status-band">
            <div>
              <p className="font-medium">{error || notice || activeJob?.message}</p>
              {activeJob && <p className="text-sm text-slate-500 dark:text-slate-400">{activeJob.state} · {activeJob.progress}%</p>}
            </div>
            {activeJob && <div className="progress"><span style={{ width: `${activeJob.progress}%` }} /></div>}
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          <WorkflowCard title="1. Upload requirements" icon={<Upload size={18} />}>
            <form className="stack" onSubmit={submitDocuments}>
              <label className="field">
                Document files
                <input type="file" multiple onChange={(event) => setFiles(event.target.files)} />
              </label>
              <label className="field">
                Server-side path
                <input placeholder="C:\\path\\to\\requirements" value={serverPath} onChange={(event) => setServerPath(event.target.value)} />
              </label>
              <button className="action-button">Index documents</button>
            </form>
          </WorkflowCard>

          <WorkflowCard title="2. Add code context" icon={<Server size={18} />}>
            <form className="stack" onSubmit={submitCode}>
              <label className="field">
                Repository URL or local path
                <input placeholder="https://github.com/org/app or C:\\repo\\src" value={sourcePath} onChange={(event) => setSourcePath(event.target.value)} />
              </label>
              <button className="action-button">Analyze source</button>
            </form>
          </WorkflowCard>

          <WorkflowCard title="3. Generate test cases" icon={<FileText size={18} />}>
            <form className="stack" onSubmit={submitGenerate}>
              <label className="field">
                Coverage goal
                <textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={5} />
              </label>
              <label className="field">
                Output format
                <select value={outputFormat} onChange={(event) => setOutputFormat(event.target.value)}>
                  {config.output_formats.map((format) => <option key={format}>{format}</option>)}
                </select>
              </label>
              <button className="action-button">Generate test cases</button>
            </form>
          </WorkflowCard>

          <WorkflowCard title="4. Generate automation" icon={<Code2 size={18} />}>
            <form className="stack" onSubmit={submitAutomation}>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="field">
                  Language
                  <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                    {config.languages.map((item) => <option key={item}>{item}</option>)}
                  </select>
                </label>
                <label className="field">
                  Framework
                  <select value={framework} onChange={(event) => setFramework(event.target.value)}>
                    {availableFrameworks.map((item) => <option key={item}>{item}</option>)}
                  </select>
                </label>
              </div>
              <button className="action-button">Create automation suite</button>
            </form>
          </WorkflowCard>
        </div>

        <div className="mt-8 grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
          <ResultPanel title="Generated test cases" artifact={testArtifact}>
            <pre className="preview">{generatedContent || 'Generated test cases will appear here.'}</pre>
          </ResultPanel>
          <ResultPanel title="Automation files" artifact={automationArtifact}>
            <div className="space-y-3">
              {automationFiles.length === 0 && <p className="empty">Generated automation files will appear here.</p>}
              {automationFiles.map((file) => (
                <details className="file-preview" key={file.name}>
                  <summary>{file.name}</summary>
                  <pre>{file.content}</pre>
                </details>
              ))}
            </div>
          </ResultPanel>
        </div>
      </section>
    </main>
  );
}

function AnimatedGrid() {
  return (
    <div className="absolute inset-0 opacity-80">
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgba(15,23,42,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.08)_1px,transparent_1px)] bg-[size:56px_56px] dark:bg-[linear-gradient(to_right,rgba(226,232,240,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(226,232,240,0.08)_1px,transparent_1px)]" />
      <motion.div
        className="absolute left-0 top-1/3 h-px w-full bg-cyan-500/40"
        animate={{ x: ['-100%', '100%'] }}
        transition={{ repeat: Infinity, duration: 7, ease: 'linear' }}
      />
    </div>
  );
}

function WorkflowCard({ title, icon, children }: { title: string; icon: JSX.Element; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <span>{icon}</span>
        <h3>{title}</h3>
      </div>
      {children}
    </section>
  );
}

function ResultPanel({ title, artifact, children }: { title: string; artifact: Artifact | null; children: React.ReactNode }) {
  return (
    <section className="panel result-panel">
      <div className="panel-title justify-between">
        <h3>{title}</h3>
        {artifact && (
          <a className="download-link" href={artifact.download_url}>
            <Download size={16} /> Download
          </a>
        )}
      </div>
      {children}
    </section>
  );
}

export default App;

