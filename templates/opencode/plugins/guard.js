// team-dev-harness 가드레일 플러그인 (opencode)
// Claude/Codex의 두 hook(block_on_owner_question, protect_tests)을 opencode 플러그인으로 포팅한다.
// 1) dev-agent-team/OWNER_QUESTION.md 에 "답: 번호"가 없으면 모든 도구 사용을 막는다.
//    판정은 **마지막** "답:" 줄만 본다(block_on_owner_question.sh 와 동기화) —
//    본문에 예시로 적힌 "답: 2" 한 줄이 정지를 그 자리에서 풀어 버리기 때문이다.
// 2) tests/ 와 test/ 밑 **커밋된** 테스트 파일의 수정/덮어쓰기를 막는다(언어 무관).
//    판정축은 파일 존재가 아니라 **git 추적 여부**다 — 존재로 판정하면 에이전트가 방금
//    만들어 아직 커밋도 안 한 자기 테스트를 스스로 못 고친다(실제로 여덟 번 재발했다).
//    추적 안 됨 -> 통과 / 추적됨 -> 차단(단 TEST_UNFREEZE.md 의 「근거:」 항목은 통과)
//    / git 없음·판정 실패 -> 차단(fail-closed).
//    python 은 tests?/ 아래 **모든 .py**(conftest.py·_contract.py·_synthetic.py 포함),
//    go(*_test.go) · rust(*_test.rs / test_*.rs) · node·ts(*.test|spec.*) · dart(*_test.dart).
//    판정 정규식·규칙은 protect_tests.sh 와 동기화한다.
// 3) bash 도구의 명령문에서도 "쓰기 위치에 온 경로"만 뽑아 같은 판정을 적용한다.
//    읽기·실행(cat/grep/pytest 등)은 절대 막지 않는다 — checker가 죽는다.
//    쓰기 대상 규칙은 protect_tests.sh 의 seg_targets 와 동기화한다.
//    셸 파싱은 휴리스틱이라 변수 확장·명령 치환으로 우회 가능하다(과속방지턱).
import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";

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
    /(^|\/)tests?\/(.*\/)?([^/]*\.py|[^/]*(_test\.(go|rs|dart)|\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs))|test_[^/]*\.rs)$/.test(
      fp.replace(/\\/g, "/")
    );

  // 경로를 프로젝트 루트 기준 상대경로로 맞춘다. 해제 목록은 사람이 쓰므로 상대경로인데
  // 편집 도구는 보통 절대경로를 넘긴다 — 안 맞추면 목록에 있는 파일을 절대경로로 고칠 때
  // 해제가 안 먹는다(protect_tests.sh 의 relroot 와 동일해야 한다).
  const relroot = (p) => {
    const q = String(p).replace(/\\/g, "/");
    const ap = path.isAbsolute(q) ? path.resolve(q) : path.resolve(root, q);
    return path.relative(path.resolve(root), ap).replace(/\\/g, "/").replace(/^\.\//, "");
  };

  // 해제 목록: 경로와 같은 줄에 「근거:」가 있는 항목만 유효하다. 읽다 실패하면
  // 빈 목록으로 보지 않고 **전면 동결**한다(fail-closed). protect_tests.sh 와 동일.
  const readUnfreeze = () => {
    const f = path.join(root, "dev-agent-team", "TEST_UNFREEZE.md");
    if (!fs.existsSync(f)) return new Set();
    let txt;
    try {
      txt = fs.readFileSync(f, "utf8");
    } catch (e) {
      throw new Error(
        "TEST_UNFREEZE.md 를 읽지 못했다. 해제 목록을 확인할 수 없으므로 전면 동결한다."
      );
    }
    const out = new Set();
    let fence = false;
    for (const ln of txt.split(/\r?\n/)) {
      // 코드블록 안은 설명용 예시다(protect_tests.sh 와 동일).
      if (ln.trimStart().startsWith("```")) { fence = !fence; continue; }
      if (fence || !ln.trimStart().startsWith("-") || !ln.includes("근거:")) continue;
      const body = ln.replace(/^\s*-\s*/, "").split("근거:")[0];
      for (const tok of body.match(/[\w./\\-]+/g) || []) {
        if (tok.includes("/") || /\.(py|go|rs|dart|js|ts|jsx|tsx)$/.test(tok)) {
          out.add(relroot(tok));
        }
      }
    }
    return out;
  };

  // null = 판정 불가(git 없음·저장소 아님). 통과로 바꾸지 않는다.
  const isTracked = (fp) => {
    let r;
    try {
      r = spawnSync("git", ["ls-files", "--error-unmatch", "--", fp], { cwd: root });
    } catch (e) {
      return null;
    }
    if (r.error) return null;
    if (r.status === 0) return true;
    const err = String(r.stderr || "");
    if (err.includes("did not match") || /no such path/i.test(err)) return false;
    return null;
  };

  const denyIfExisting = (fp) => {
    if (!fp || !isTestFile(fp)) return;
    const norm = relroot(fp);
    const t = isTracked(fp);
    if (t === null) {
      throw new Error(
        `git 으로 추적 여부를 가릴 수 없어 테스트 보호를 확인하지 못했다: ${fp}. ` +
          "못 가린 것을 통과로 바꾸지 않는다."
      );
    }
    if (t && !readUnfreeze().has(norm)) {
      throw new Error(
        `커밋된 테스트 파일은 수정 금지다: ${fp}. 근거가 있으면 ` +
          "dev-agent-team/TEST_UNFREEZE.md 에 경로와 「근거:」를 함께 적어라."
      );
    }
  };

  return {
    "tool.execute.before": async (input, output) => {
      // 1. 미답변 Owner 질문이 있으면 차단
      const q = path.join(root, "dev-agent-team", "OWNER_QUESTION.md");
      if (fs.existsSync(q)) {
        const txt = fs.readFileSync(q, "utf8");
        const answerLines = txt.split(/\r?\n/).filter((l) => /^답:/.test(l));
        const lastAnswer = answerLines.length ? answerLines[answerLines.length - 1] : "";
        if (!/^답:\s*[0-9]/.test(lastAnswer)) {
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
