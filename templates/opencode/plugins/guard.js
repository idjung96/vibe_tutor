// team-dev-harness 가드레일 플러그인 (opencode)
// Claude/Codex의 두 hook(block_on_owner_question, protect_tests)을 opencode 플러그인으로 포팅한다.
// 1) dev-agent-team/OWNER_QUESTION.md 에 "답: 번호"가 없으면 모든 도구 사용을 막는다.
// 2) tests/ 와 test/ 밑 기존 테스트 파일의 수정/덮어쓰기를 막는다(언어 무관).
//    python(*_test.py / test_*.py) · go(*_test.go) · rust(*_test.rs / test_*.rs)
//    · node·ts(*.test.{js,jsx,ts,tsx,mjs,cjs} / *.spec.{...}) · dart(*_test.dart).
//    판정 정규식은 protect_tests.sh 의 TEST_RE 와 동기화한다.
// 3) bash 도구의 명령문에서도 "쓰기 위치에 온 경로"만 뽑아 같은 판정을 적용한다.
//    읽기·실행(cat/grep/pytest 등)은 절대 막지 않는다 — checker가 죽는다.
//    쓰기 대상 규칙은 protect_tests.sh 의 seg_targets 와 동기화한다.
//    셸 파싱은 휴리스틱이라 변수 확장·명령 치환으로 우회 가능하다(과속방지턱).
import fs from "fs";
import path from "path";

// 비플래그 인자 전부가 쓰기 대상인 명령들
const WRITE_ALL = ["tee", "mv", "rm", "truncate", "patch"];
// 앞에 붙어도 실제 명령이 아닌 래퍼들
const SKIP_HEAD = ["sudo", "env", "command", "nohup", "time", "xargs"];

const baseName = (p) => p.replace(/\\/g, "/").split("/").pop();

const tokenize = (s) => {
  const out = [];
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    out.push(m[1] !== undefined ? m[1] : m[2] !== undefined ? m[2] : m[3]);
  }
  return out;
};

// 한 개의 단순 명령에서 쓰기 대상 경로만 뽑는다.
const segTargets = (seg) => {
  const res = [];
  const redir = />>?\s*([^\s;|&<>()]+)/g;
  let m;
  while ((m = redir.exec(seg)) !== null) res.push(m[1]);
  const body = seg.replace(/\d*>>?\s*[^\s;|&<>()]+/g, " ");
  let argv = tokenize(body);
  while (argv.length && (argv[0].includes("=") || SKIP_HEAD.includes(baseName(argv[0])))) {
    argv = argv.slice(1);
  }
  if (argv.length === 0) return res;
  const name = baseName(argv[0]);
  const rest = argv.slice(1);
  const args = rest.filter((a) => !a.startsWith("-"));
  if (WRITE_ALL.includes(name)) {
    res.push(...args);
  } else if (name === "cp") {
    if (args.length) res.push(args[args.length - 1]);
  } else if (name === "sed") {
    const inplace = rest.some(
      (a) => a === "--in-place" || a.startsWith("--in-place=") || /^-[a-zA-Z]*i/.test(a)
    );
    if (inplace) res.push(...args);
  } else if (name === "dd") {
    for (const a of rest) if (a.startsWith("of=")) res.push(a.slice(3));
  }
  return res;
};

const bashWriteTargets = (cmd) => {
  const out = [];
  for (const seg of String(cmd).split(/[;\n]|\|\||&&|\|/)) out.push(...segTargets(seg));
  return out;
};

export const TeamGuard = async ({ directory }) => {
  const root = directory || process.cwd();
  const isTestFile = (fp) =>
    /(^|\/)tests?\/(.*\/)?([^/]*(_test\.(py|go|rs|dart)|\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs))|test_[^/]*\.(py|rs))$/.test(
      fp.replace(/\\/g, "/")
    );
  const denyIfExisting = (fp) => {
    if (!fp || !isTestFile(fp)) return;
    const abs = path.isAbsolute(fp) ? fp : path.join(root, fp);
    if (fs.existsSync(abs)) {
      throw new Error(
        "기존 테스트 파일은 수정 금지다. 틀렸다고 판단되면 C등급으로 Owner에게 물어라."
      );
    }
  };

  return {
    "tool.execute.before": async (input, output) => {
      // 1. 미답변 Owner 질문이 있으면 차단
      const q = path.join(root, "dev-agent-team", "OWNER_QUESTION.md");
      if (fs.existsSync(q)) {
        const txt = fs.readFileSync(q, "utf8");
        if (!/^답:\s*[0-9]/m.test(txt)) {
          throw new Error(
            "Owner 답변 대기 중: dev-agent-team/OWNER_QUESTION.md의 '답:'에 번호가 적힐 때까지 멈춘다."
          );
        }
      }
      // 2. 기존 테스트 파일 보호
      const tool = input && input.tool;
      const args = (output && output.args) || {};
      if (tool === "edit" || tool === "write" || tool === "patch") {
        denyIfExisting(args.filePath || args.path || args.file || "");
      }
      // 3. bash 경유 우회 차단 (쓰기 대상만)
      if (tool === "bash" && args.command) {
        for (const t of bashWriteTargets(args.command)) denyIfExisting(t);
      }
    },
  };
};
