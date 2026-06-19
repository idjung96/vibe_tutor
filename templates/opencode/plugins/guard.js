// team-dev-harness 가드레일 플러그인 (opencode)
// Claude/Codex의 두 hook(block_on_owner_question, protect_tests)을 opencode 플러그인으로 포팅한다.
// 1) dev-agent-team/OWNER_QUESTION.md 에 "답: 번호"가 없으면 모든 도구 사용을 막는다.
// 2) 기존 tests/*_test.py · tests/test_*.py 의 수정/덮어쓰기를 막는다.
import fs from "fs";
import path from "path";

export const TeamGuard = async ({ directory }) => {
  const root = directory || process.cwd();
  const isTestFile = (fp) =>
    /(^|\/)tests\/([^/]*_test\.py|test_[^/]*\.py)$/.test(fp.replace(/\\/g, "/"));

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
      if (tool === "edit" || tool === "write" || tool === "patch") {
        const args = (output && output.args) || {};
        const fp = args.filePath || args.path || args.file || "";
        if (fp && isTestFile(fp)) {
          const abs = path.isAbsolute(fp) ? fp : path.join(root, fp);
          if (fs.existsSync(abs)) {
            throw new Error(
              "기존 테스트 파일은 수정 금지다. 틀렸다고 판단되면 C등급으로 Owner에게 물어라."
            );
          }
        }
      }
    },
  };
};
