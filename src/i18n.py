from src import config as _cfg

_STRINGS: dict[str, dict[str, str]] = {
    # ── Menu ──────────────────────────────────────────────────────────────────
    "menu_file":            {"pt": "Arquivo",           "en": "File"},
    "menu_open":            {"pt": "Abrir STL / OBJ...", "en": "Open STL / OBJ..."},
    "menu_export_zip":      {"pt": "Exportar partes como ZIP...", "en": "Export parts as ZIP..."},
    "menu_export_single":   {"pt": "Exportar parte selecionada...", "en": "Export selected part..."},
    "menu_quit":            {"pt": "Sair",              "en": "Quit"},
    "menu_view":            {"pt": "Visualizar",        "en": "View"},
    "menu_wireframe":       {"pt": "Alternar Wireframe\tW", "en": "Toggle Wireframe\tW"},
    "menu_exploded":        {"pt": "Vista explodida\tE", "en": "Exploded view\tE"},
    "menu_fit":             {"pt": "Enquadrar câmera\tF", "en": "Fit camera\tF"},
    "menu_help":            {"pt": "Ajuda",             "en": "Help"},
    "menu_about":           {"pt": "Sobre",             "en": "About"},
    "menu_language":        {"pt": "Idioma",            "en": "Language"},
    "menu_lang_pt":         {"pt": "Português (PT-BR)", "en": "Portuguese (PT-BR)"},
    "menu_lang_en":         {"pt": "English",           "en": "English"},

    # ── Status bar ────────────────────────────────────────────────────────────
    "status_ready":         {"pt": "Pronto. Abra um arquivo STL ou OBJ para começar.",
                             "en": "Ready. Open an STL or OBJ file to begin."},
    "status_loading":       {"pt": "Carregando modelo...", "en": "Loading model..."},
    "status_simplifying":   {"pt": "Simplificando mesh (aguarde)...", "en": "Simplifying mesh (please wait)..."},
    "status_cutting":       {"pt": "Cortando '{name}' em {ax} = {pos:.2f} mm...",
                             "en": "Cutting '{name}' on {ax} = {pos:.2f} mm..."},
    "status_analyzing":     {"pt": "Analisando componentes de '{name}'...",
                             "en": "Analyzing components of '{name}'..."},
    "status_ai_detecting":  {"pt": "IA detectando região (ângulo {angle:.0f}°)...",
                             "en": "AI detecting region (angle {angle:.0f}°)..."},
    "status_joint_detect":  {"pt": "Detectando encaixe para '{name}'...",
                             "en": "Detecting joint for '{name}'..."},
    "status_exporting_zip": {"pt": "Exportando ZIP...", "en": "Exporting ZIP..."},
    "status_exporting":     {"pt": "Exportando '{name}'...", "en": "Exporting '{name}'..."},
    "status_error_load":    {"pt": "Erro ao carregar arquivo.", "en": "Error loading file."},
    "status_error_cut":     {"pt": "Erro no corte.", "en": "Cut error."},
    "status_error_joint":   {"pt": "Erro nos encaixes.", "en": "Joint error."},
    "status_error_comp":    {"pt": "Erro ao separar componentes.", "en": "Error splitting components."},
    "status_error_export":  {"pt": "Erro na exportação.", "en": "Export error."},
    "status_nothing_undo":  {"pt": "Nada para desfazer.", "en": "Nothing to undo."},
    "status_undo":          {"pt": "Operação desfeita  |  {n} restante(s)", "en": "Undone  |  {n} remaining"},
    "status_reset":         {"pt": "Resetado ao modelo original.", "en": "Reset to original model."},
    "status_paint_off":     {"pt": "Modo de pintura desativado.", "en": "Paint mode deactivated."},
    "status_normal_view":   {"pt": "Vista normal.", "en": "Normal view."},
    "status_renamed":       {"pt": "Renomeado: '{old}' → '{new}'", "en": "Renamed: '{old}' → '{new}'"},
    "status_cut_done":      {"pt": "Corte: '{a}' e '{b}'  |  Total: {n} partes",
                             "en": "Cut: '{a}' and '{b}'  |  Total: {n} parts"},
    "status_joint_done":    {"pt": "Encaixe: pino em '{a}', furo em '{b}'",
                             "en": "Joint: pin in '{a}', hole in '{b}'"},
    "status_joint_warns":   {"pt": "Encaixe: pino em '{a}', furo em '{b}' ({n} aviso(s))",
                             "en": "Joint: pin in '{a}', hole in '{b}' ({n} warning(s))"},
    "status_selected":      {"pt": "Selecionado: '{name}'  —  clique 'Separar + Encaixar Auto' para gerar o encaixe",
                             "en": "Selected: '{name}'  —  click 'Split + Auto Joint' to generate the joint"},
    "status_simplified":    {"pt": "Simplificado: {n:,} faces.", "en": "Simplified: {n:,} faces."},
    "status_exported":      {"pt": "Exportado: {path}", "en": "Exported: {path}"},
    "status_exported_part": {"pt": "'{name}' exportado: {path}", "en": "'{name}' exported: {path}"},
    "status_single_comp":   {"pt": "'{name}' já é um único componente.", "en": "'{name}' is already a single component."},
    "status_divided":       {"pt": "Dividido: '{a}' + '{b}'. Gerando encaixe...",
                             "en": "Split: '{a}' + '{b}'. Generating joint..."},
    "status_paint_one":     {"pt": "IA ativa — clique na parte que deseja separar. Ângulo limite: {angle:.0f}°",
                             "en": "AI active — click the part you want to separate. Angle limit: {angle:.0f}°"},
    "status_paint_many":    {"pt": "IA ativa — clique na parte desejada ({n} componentes detectados).",
                             "en": "AI active — click the desired part ({n} components detected)."},
    "status_paint_cancel":  {"pt": "Seleção cancelada. Ajuste o ângulo e tente novamente.",
                             "en": "Selection cancelled. Adjust the angle and try again."},
    "status_exploded":      {"pt": "Vista explodida — {n} peça(s) separadas para visualização. Tecla E para fechar.",
                             "en": "Exploded view — {n} part(s) separated for visualization. Press E to close."},
    "status_comp_done":     {"pt": "'{name}' → {n} componentes  |  Total: {total}",
                             "en": "'{name}' → {n} components  |  Total: {total}"},
    "status_log_path":      {"pt": "Log salvo em: {path}", "en": "Log saved at: {path}"},
    "status_lang_restart":  {"pt": "Idioma alterado. Reinicie o aplicativo para aplicar.",
                             "en": "Language changed. Restart the application to apply."},

    # ── Botões ────────────────────────────────────────────────────────────────
    "btn_open":             {"pt": "Abrir STL / OBJ", "en": "Open STL / OBJ"},
    "btn_paint":            {"pt": "Pintar Parte  (clique na mesh)", "en": "Paint Part  (click on mesh)"},
    "btn_auto_join":        {"pt": "Separar + Encaixar Auto", "en": "Split + Auto Joint"},
    "btn_wireframe":        {"pt": "Wireframe  [W]", "en": "Wireframe  [W]"},
    "btn_cut":              {"pt": "Aplicar Corte", "en": "Apply Cut"},
    "btn_split_comp":       {"pt": "Separar Componentes", "en": "Split Components"},
    "btn_add_joint":        {"pt": "Adicionar Encaixe à Parte Selecionada", "en": "Add Joint to Selected Part"},
    "btn_undo":             {"pt": "Desfazer", "en": "Undo"},
    "btn_reset":            {"pt": "Resetar", "en": "Reset"},
    "btn_fit":              {"pt": "Enquadrar", "en": "Fit"},
    "btn_explode":          {"pt": "Vista Explodida  [E]", "en": "Exploded View  [E]"},
    "btn_export_zip":       {"pt": "Exportar ZIP", "en": "Export ZIP"},
    "btn_export_part":      {"pt": "Exportar Parte", "en": "Export Part"},

    # ── Labels / GroupBoxes ───────────────────────────────────────────────────
    "grp_info":             {"pt": "Informações do modelo", "en": "Model Information"},
    "grp_paint":            {"pt": "Pintar e Separar  (IA)", "en": "Paint and Split  (AI)"},
    "grp_cut":              {"pt": "Corte por plano  (manual)", "en": "Plane Cut  (manual)"},
    "grp_joint":            {"pt": "Parâmetros do encaixe", "en": "Joint Parameters"},
    "grp_parts":            {"pt": "Partes  (duplo-clique para renomear)", "en": "Parts  (double-click to rename)"},
    "lbl_axis":             {"pt": "Eixo:", "en": "Axis:"},
    "lbl_position":         {"pt": "Posição:", "en": "Position:"},
    "lbl_position_val":     {"pt": "Posição: {v:.2f} mm", "en": "Position: {v:.2f} mm"},
    "lbl_position_empty":   {"pt": "Posição: —", "en": "Position: —"},
    "lbl_angle":            {"pt": "Ângulo limite:", "en": "Angle limit:"},
    "lbl_diam":             {"pt": "Diâm. pino:", "en": "Pin diam.:"},
    "lbl_depth":            {"pt": "Prof. pino:", "en": "Pin depth:"},
    "lbl_tol":              {"pt": "Tolerância:", "en": "Tolerance:"},
    "lbl_pins":             {"pt": "Qtd. pinos:", "en": "Pin count:"},
    "lbl_name":             {"pt": "Vértices: —", "en": "Vertices: —"},
    "lbl_verts_val":        {"pt": "Vértices: {n:,}", "en": "Vertices: {n:,}"},
    "lbl_faces_val":        {"pt": "Faces: {n:,}", "en": "Faces: {n:,}"},
    "lbl_dims_val":         {"pt": "Dims: {x:.1f} × {y:.1f} × {z:.1f} mm",
                             "en": "Dims: {x:.1f} × {y:.1f} × {z:.1f} mm"},
    "lbl_unit_val":         {"pt": "Unidade: {v}", "en": "Unit: {v}"},
    "lbl_wt_yes":           {"pt": "Watertight: Sim", "en": "Watertight: Yes"},
    "lbl_wt_no":            {"pt": "Watertight: Não", "en": "Watertight: No"},
    "lbl_comp_val":         {"pt": "Componentes: {n}", "en": "Components: {n}"},
    "lbl_comp_auto":        {"pt": "Componentes: {n} — separados automaticamente",
                             "en": "Components: {n} — automatically separated"},
    "paint_hint":           {"pt": "Clique em uma parte do modelo para selecioná-la.\nA IA detecta os limites automaticamente.",
                             "en": "Click on a part of the model to select it.\nAI detects boundaries automatically."},

    # ── Tooltips ──────────────────────────────────────────────────────────────
    "tip_export_part":      {"pt": "Exporta somente a parte selecionada (STL ou OBJ)",
                             "en": "Exports only the selected part (STL or OBJ)"},
    "tip_auto_join":        {"pt": "Gera encaixe automático entre a parte selecionada\ne o componente adjacente mais próximo.",
                             "en": "Generates automatic joint between the selected part\nand the nearest adjacent component."},
    "tip_angle":            {"pt": "Ângulo de parada da pintura.\n30° = padrão (detecta bordas nítidas).\nReduza para selecionar regiões menores (ex: olho).\nAumente se a seleção parar cedo demais.",
                             "en": "Paint stop angle.\n30° = default (detects sharp edges).\nDecrease to select smaller regions.\nIncrease if selection stops too early."},
    "tip_split_comp":       {"pt": "Divide a parte selecionada nos seus corpos separados",
                             "en": "Splits the selected part into its separate bodies"},
    "tip_explode":          {"pt": "Afasta as peças para visualizar como vão ficar\nseparadas na impressora 3D.",
                             "en": "Separates parts to visualize how they will look\napart on the 3D printer."},

    # ── Diálogos ──────────────────────────────────────────────────────────────
    "dlg_open_title":       {"pt": "Abrir modelo 3D", "en": "Open 3D model"},
    "dlg_open_filter":      {"pt": "Modelos 3D (*.stl *.obj *.STL *.OBJ)", "en": "3D Models (*.stl *.obj *.STL *.OBJ)"},
    "dlg_heavy_title":      {"pt": "Modelo pesado detectado", "en": "Heavy model detected"},
    "dlg_heavy_msg":        {"pt": "Este modelo tem {n:,} faces ({m:.1f}M).\n\nOperações de encaixe (booleanas) podem ser muito lentas.\n\nDeseja simplificar para ~{t:,} faces?\n(O arquivo original não é modificado.)",
                             "en": "This model has {n:,} faces ({m:.1f}M).\n\nJoint operations (booleans) may be very slow.\n\nSimplify to ~{t:,} faces?\n(Original file is not modified.)"},
    "dlg_region_title":     {"pt": "Região detectada pela IA", "en": "Region detected by AI"},
    "dlg_region_msg":       {"pt": "Parte pintada: {pf:,} faces  ({pp:.0f}%)  {wtp}\nBase: {bf:,} faces  ({bp:.0f}%)  {wtb}\n\nDeseja separar e gerar encaixe automático?\n\n(Se a seleção ficou errada, clique Não, ajuste o ângulo e tente novamente.)",
                             "en": "Painted part: {pf:,} faces  ({pp:.0f}%)  {wtp}\nBase: {bf:,} faces  ({bp:.0f}%)  {wtb}\n\nSplit and generate automatic joint?\n\n(If the selection is wrong, click No, adjust the angle and try again.)"},
    "dlg_wt_closed":        {"pt": "✓ fechada", "en": "✓ closed"},
    "dlg_wt_open":          {"pt": "⚠ aberta", "en": "⚠ open"},
    "dlg_export_zip_title": {"pt": "Salvar ZIP", "en": "Save ZIP"},
    "dlg_export_fmt_title": {"pt": "Formato dos arquivos", "en": "File format"},
    "dlg_export_fmt_label": {"pt": "Formato:", "en": "Format:"},
    "dlg_export_fmt_stl":   {"pt": "STL  (.stl) — recomendado para impressão", "en": "STL  (.stl) — recommended for printing"},
    "dlg_export_fmt_obj":   {"pt": "OBJ  (.obj)", "en": "OBJ  (.obj)"},
    "dlg_export_part_title":{"pt": "Salvar parte", "en": "Save part"},
    "dlg_rename_title":     {"pt": "Renomear Parte", "en": "Rename Part"},
    "dlg_rename_label":     {"pt": "Novo nome:", "en": "New name:"},
    "dlg_export_ok_title":  {"pt": "Exportado!", "en": "Exported!"},
    "dlg_export_ok_zip":    {"pt": "{n} parte(s) salvas em:\n{path}", "en": "{n} part(s) saved at:\n{path}"},
    "dlg_export_ok_part":   {"pt": "'{name}' salvo em:\n{path}", "en": "'{name}' saved at:\n{path}"},
    "dlg_export_one_warn":  {"pt": "Só há uma parte. Deseja exportar mesmo assim?", "en": "Only one part exists. Export anyway?"},
    "dlg_export_one_title": {"pt": "Exportar", "en": "Export"},
    "dlg_no_parts":         {"pt": "Nenhum modelo carregado.", "en": "No model loaded."},
    "dlg_need_cut":         {"pt": "Faça pelo menos um corte antes de adicionar encaixes.", "en": "Make at least one cut before adding joints."},
    "dlg_need_next":        {"pt": "Selecione uma parte que tenha outra logo abaixo na lista.", "en": "Select a part that has another one below it in the list."},
    "dlg_one_part_warn":    {"pt": "Só há uma parte no modelo.\n\nUse 'Pintar Parte' para selecionar uma região,\nou 'Separar Componentes' se o modelo tiver partes separadas.",
                             "en": "Only one part in the model.\n\nUse 'Paint Part' to select a region,\nor 'Split Components' if the model has separate parts."},
    "dlg_single_comp":      {"pt": "'{name}' não possui corpos separados.\nUse 'Pintar Parte' para separar por região,\nou o slider de corte manual.",
                             "en": "'{name}' has no separate bodies.\nUse 'Paint Part' to separate by region,\nor the manual cut slider."},
    "dlg_comp_title":       {"pt": "Componentes", "en": "Components"},
    "dlg_err_cut":          {"pt": "Erro no corte", "en": "Cut error"},
    "dlg_err_paint":        {"pt": "Erro na pintura", "en": "Paint error"},
    "dlg_err_paint_msg":    {"pt": "{err}\n\nDicas:\n• Tente clicar mais próximo do centro da parte desejada\n• Ajuste o ângulo limite (menor = bordas mais nítidas)\n• 30° = padrão  |  15° = bordas finas  |  45° = regiões largas",
                             "en": "{err}\n\nTips:\n• Try clicking closer to the center of the desired part\n• Adjust the angle limit (lower = sharper edges)\n• 30° = default  |  15° = thin edges  |  45° = large regions"},
    "dlg_err_auto_joint":   {"pt": "Erro no encaixe automático:\n{err}", "en": "Error in auto joint:\n{err}"},
    "dlg_err_joint":        {"pt": "Erro ao adicionar encaixes:\n{err}", "en": "Error adding joints:\n{err}"},
    "dlg_err_export":       {"pt": "Erro na exportação", "en": "Export error"},
    "dlg_warn_joint":       {"pt": "Avisos nos encaixes", "en": "Joint warnings"},
    "dlg_warn_joint_msg":   {"pt": "Encaixes gerados com avisos:\n• {warns}", "en": "Joints generated with warnings:\n• {warns}"},
    "dlg_warn_joint_msg2":  {"pt": "Encaixes adicionados com avisos:\n• {warns}", "en": "Joints added with warnings:\n• {warns}"},
    "dlg_warn_title":       {"pt": "Aviso", "en": "Warning"},

    # ── Sobre ─────────────────────────────────────────────────────────────────
    "about_title":          {"pt": "Sobre — ZefiroSplit", "en": "About — ZefiroSplit"},
    "about_text":           {
        "pt": (
            "ZefiroSplit  |  Zefiro3D\n\n"
            "COMO USAR:\n"
            "1. Abra um STL ou OBJ\n"
            "2. Clique 'Pintar Parte' e clique na parte desejada\n"
            "   → A IA detecta os limites e separa automaticamente\n"
            "   → Encaixe macho/fêmea gerado automaticamente\n"
            "3. Vista Explodida [E] para visualizar as peças separadas\n"
            "4. Exporte como ZIP (todas) ou STL/OBJ (parte individual)\n\n"
            "ATALHOS:\n"
            "  W — Wireframe\n"
            "  E — Vista explodida\n"
            "  F — Enquadrar câmera\n"
            "  Duplo-clique na lista — Renomear parte\n\n"
            "CORTE MANUAL:\n"
            "  Use o slider e 'Aplicar Corte' para cortes precisos por plano."
        ),
        "en": (
            "ZefiroSplit  |  Zefiro3D\n\n"
            "HOW TO USE:\n"
            "1. Open an STL or OBJ\n"
            "2. Click 'Paint Part' and click the desired part\n"
            "   → AI detects boundaries and splits automatically\n"
            "   → Male/female joint generated automatically\n"
            "3. Exploded View [E] to visualize separated parts\n"
            "4. Export as ZIP (all) or STL/OBJ (individual part)\n\n"
            "SHORTCUTS:\n"
            "  W — Wireframe\n"
            "  E — Exploded view\n"
            "  F — Fit camera\n"
            "  Double-click on list — Rename part\n\n"
            "MANUAL CUT:\n"
            "  Use the slider and 'Apply Cut' for precise plane cuts."
        ),
    },

    # ── Info de carregamento ──────────────────────────────────────────────────
    "load_status_single":   {"pt": "{name}  |  {faces:,} faces  |  Use 'Pintar Parte' para separar uma região",
                             "en": "{name}  |  {faces:,} faces  |  Use 'Paint Part' to separate a region"},
    "load_status_multi":    {"pt": "{name}  |  {faces:,} faces  |  {n} partes detectadas — use 'Pintar Parte' para selecionar",
                             "en": "{name}  |  {faces:,} faces  |  {n} parts detected — use 'Paint Part' to select"},
}


def tr(key: str, **kwargs) -> str:
    lang = _cfg.get_language()
    entry = _STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("pt") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
