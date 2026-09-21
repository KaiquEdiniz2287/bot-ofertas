# Skill: Semantic Versioning

Use Semantic Versioning 2.0.0 seguindo o padrão:

`MAJOR.MINOR.PATCH`

Referência: semver.org

Sempre que uma implementação for concluída, analise se a versão do projeto precisa ser incrementada.

## Regras

### PATCH

Incrementar apenas o último número.

Exemplo:
`1.4.2 → 1.4.3`

Use para:

- correções de bugs;
- pequenos ajustes visuais;
- otimizações;
- refatorações internas;
- melhorias sem nova funcionalidade relevante;
- alterações compatíveis com a versão atual.

Regra mental:

`PATCH = corrigi`

### MINOR

Incrementar o número do meio e zerar PATCH.

Exemplo:
`1.4.3 → 1.5.0`

Use para:

- novas funcionalidades;
- novos recursos;
- novas páginas;
- novas integrações;
- melhorias funcionais relevantes;
- alterações compatíveis com funcionalidades existentes.

Regra mental:

`MINOR = adicionei`

### MAJOR

Incrementar o primeiro número e zerar MINOR e PATCH.

Exemplo:
`1.5.3 → 2.0.0`

Use para:

- breaking changes;
- alterações incompatíveis;
- grandes mudanças de arquitetura;
- mudanças que exigem migração;
- remoção ou alteração incompatível de APIs ou funcionalidades existentes.

Regra mental:

`MAJOR = quebrei ou reformulei`

## Projetos em versão 0.x

Enquanto o projeto ainda estiver em desenvolvimento inicial, mantenha versões `0.x.x`.

Use PATCH para pequenas correções e MINOR para funcionalidades ou mudanças relevantes.

Somente avance para `1.0.0` quando o projeto for considerado estável e pronto para seu primeiro lançamento oficial.

## Procedimento

Antes de alterar a versão:

1. Identifique a versão atual do projeto.
2. Analise todas as mudanças concluídas desde o último incremento.
3. Determine o maior nível necessário: PATCH, MINOR ou MAJOR.
4. Atualize a versão somente uma vez para o conjunto da implementação.
5. Não incremente a versão em cada pequeno commit ou etapa intermediária.
6. Informe ao final:
   - versão anterior;
   - nova versão;
   - nível aplicado;
   - motivo.

Exemplo:

`Versão: 1.4.2 → 1.5.0`
`Tipo: MINOR`
`Motivo: adição de uma nova funcionalidade sem breaking changes.`

Não altere versões automaticamente quando nenhuma mudança relevante tiver sido concluída.
