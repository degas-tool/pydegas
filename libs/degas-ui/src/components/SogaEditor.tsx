import Editor, { type BeforeMount, type OnChange } from "@monaco-editor/react";
import { defineEditorThemes, EDITOR_THEME } from "../monaco-theme";

const LANG = "soga";

function registerLanguage(monaco: Parameters<BeforeMount>[0]) {
  defineEditorThemes(monaco);
  if (
    monaco.languages.getLanguages().find((l: { id: string }) => l.id === LANG)
  )
    return;

  monaco.languages.register({ id: LANG });

  monaco.languages.setMonarchTokensProvider(LANG, {
    keywords: [
      "for",
      "in",
      "range",
      "end",
      "if",
      "else",
      "observe",
      "skip",
      "prune",
      "array",
      "data",
    ],
    builtins: ["gauss", "gm", "uniform", "beta", "bern"],
    tokenizer: {
      root: [
        [/\/\*/, "comment", "@blockComment"],
        [/_[a-zA-Z]\w*/, "parameter"],
        [
          /[a-zA-Z_]\w*/,
          {
            cases: {
              "@keywords": "keyword",
              "@builtins": "type",
              "@default": "identifier",
            },
          },
        ],
        [/\d+\.?\d*/, "number"],
        [/[+\-*/<>=!]/, "operator"],
        [/[{}()[\]]/, "delimiter"],
        [/[,;]/, "delimiter"],
      ],
      blockComment: [
        [/[^/*]+/, "comment"],
        [/\*\//, "comment", "@pop"],
        [/[/*]/, "comment"],
      ],
    },
  });
}

type Props = {
  theme: "light" | "dark";
  value: string;
  onChange: OnChange;
};

export function SogaEditor({ theme, value, onChange }: Props) {
  return (
    <Editor
      height="100%"
      language={LANG}
      theme={EDITOR_THEME[theme]}
      value={value}
      onChange={onChange}
      beforeMount={registerLanguage}
      options={{
        fontSize: 13,
        lineHeight: 22,
        fontFamily: "Menlo, Consolas, 'Courier New', monospace",
        fontLigatures: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderLineHighlight: "line",
        padding: { top: 16, bottom: 16 },
        tabSize: 4,
        wordWrap: "on",
        smoothScrolling: true,
      }}
    />
  );
}
