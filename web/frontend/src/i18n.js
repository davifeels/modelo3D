const STRINGS = {
  // Header
  app_name:          { pt: 'ZefiroSplit', en: 'ZefiroSplit' },
  lang_pt:           { pt: '🇧🇷 PT', en: '🇧🇷 PT' },
  lang_en:           { pt: '🇺🇸 EN', en: '🇺🇸 EN' },
  theme_light:       { pt: 'Tema claro', en: 'Light theme' },
  theme_dark:        { pt: 'Tema escuro', en: 'Dark theme' },
  toolbar_open:      { pt: 'Abrir arquivo', en: 'Open file' },
  toolbar_undo:      { pt: 'Desfazer', en: 'Undo' },

  // Steps
  step_import:       { pt: 'Importar', en: 'Import' },
  step_cut:          { pt: 'Cortar', en: 'Cut' },
  step_paint:        { pt: 'Pintar', en: 'Paint' },
  step_preview:      { pt: 'Preview', en: 'Preview' },
  step_process:      { pt: 'Processar', en: 'Process' },
  step_export:       { pt: 'Exportar', en: 'Export' },

  // Status bar
  status_idle:       { pt: 'Aguardando modelo', en: 'Waiting for model' },
  status_loaded:     { pt: 'Modelo carregado', en: 'Model loaded' },
  status_cutting:    { pt: 'Ajustando plano de corte', en: 'Adjusting cut plane' },
  status_painting:   { pt: 'Pintando seleção', en: 'Painting selection' },
  status_previewing: { pt: 'Preview dos encaixes', en: 'Joint preview' },
  status_processing: { pt: 'Processando', en: 'Processing' },
  status_result:     { pt: 'Pronto para exportar', en: 'Ready to export' },
  status_faces:      { pt: 'faces', en: 'faces' },
  status_painted:    { pt: 'pintadas', en: 'painted' },

  // Upload progress
  upload_reading:    { pt: 'Lendo arquivo…', en: 'Reading file…' },
  upload_parsing:    { pt: 'Analisando geometria…', en: 'Analyzing geometry…' },
  upload_done:       { pt: 'Carregando visualização…', en: 'Loading visualization…' },

  // DropZone
  drop_title:        { pt: 'Arraste seu modelo 3D aqui', en: 'Drag your 3D model here' },
  drop_or:           { pt: 'ou', en: 'or' },
  drop_btn:          { pt: 'Selecionar arquivo', en: 'Select file' },
  drop_formats:      { pt: 'Suporta STL e OBJ', en: 'Supports STL and OBJ' },
  drop_drag_over:    { pt: 'Solte para carregar', en: 'Drop to load' },
  err_format:        { pt: 'Formato não suportado. Use STL ou OBJ.', en: 'Unsupported format. Use STL or OBJ.' },
  warn_scaled:       { pt: '⚠️ Arquivo estava em {unit} — convertido automaticamente para mm.', en: '⚠️ File was in {unit} — automatically converted to mm.' },
  warn_holes:        { pt: '⚠️ A malha tem buracos que não puderam ser reparados automaticamente. O corte ainda funciona, mas verifique as peças antes de imprimir.', en: '⚠️ The mesh has holes that could not be repaired automatically. Cutting still works, but check the parts before printing.' },
  info_repaired:     { pt: 'Buracos pequenos foram reparados automaticamente.', en: 'Small holes were repaired automatically.' },
  unit_m:            { pt: 'metros', en: 'meters' },
  unit_cm:           { pt: 'centímetros', en: 'centimeters' },
  unit_um:           { pt: 'micrômetros', en: 'micrometers' },
  dims_label:        { pt: 'Dimensões', en: 'Dimensions' },

  // Info panel
  info_title:        { pt: 'Informações do Modelo', en: 'Model Info' },
  info_filename:     { pt: 'Nome do arquivo', en: 'File name' },
  info_vertices:     { pt: 'Vértices', en: 'Vertices' },
  info_faces:        { pt: 'Faces (triângulos)', en: 'Faces (triangles)' },
  info_dims:         { pt: 'Dimensões (X, Y, Z)', en: 'Dimensions (X, Y, Z)' },
  info_unit:         { pt: 'Unidade', en: 'Unit' },
  info_watertight:   { pt: 'Status da malha', en: 'Mesh status' },
  info_wt_ok:        { pt: 'Watertight', en: 'Watertight' },
  info_wt_open:      { pt: 'Malha aberta', en: 'Open mesh' },
  info_components:   { pt: 'Componentes', en: 'Components' },
  info_volume:       { pt: 'Volume', en: 'Volume' },
  info_painted:      { pt: 'Faces pintadas', en: 'Painted faces' },

  // Side panel
  general_tools:     { pt: 'Ferramentas Gerais', en: 'General Tools' },
  reset_camera:      { pt: 'Resetar câmera', en: 'Reset camera' },
  show_wireframe:    { pt: 'Exibir wireframe', en: 'Show wireframe' },
  show_grid:         { pt: 'Exibir grade', en: 'Show grid' },
  center_model:      { pt: 'Centralizar modelo', en: 'Center model' },
  clear_selection:   { pt: 'Limpar seleção', en: 'Clear selection' },
  tips_title:        { pt: 'Dicas de uso', en: 'Usage tips' },
  tip_paint_html:    { pt: 'Pinte a região que será a <b> (vermelha, recebe as cavidades). A área não pintada será a <a> (azul, recebe os pinos).', en: 'Paint the region that becomes <b> (red, gets the cavities). The unpainted area becomes <a> (blue, gets the pins).' },
  tip_undo:          { pt: 'Use Ctrl+Z para desfazer.', en: 'Use Ctrl+Z to undo.' },

  // Right panel — headers por etapa
  rp_auto_cut:       { pt: 'Corte Automático', en: 'Automatic Cut' },
  rp_adjust_cut:     { pt: 'Ajustar Corte', en: 'Adjust Cut' },
  rp_manual_sel:     { pt: 'Seleção Manual', en: 'Manual Selection' },
  rp_preview:        { pt: 'Preview dos Encaixes', en: 'Joint Preview' },
  rp_view_export:    { pt: 'Visualização e Exportação', en: 'View & Export' },
  rp_tools:          { pt: 'Ferramentas', en: 'Tools' },

  // Auto cut
  smart_cut_title:   { pt: 'Corte inteligente', en: 'Smart cut' },
  smart_cut_desc:    { pt: 'A IA analisa o modelo e detecta automaticamente os melhores pontos de corte — cintura, pescoço, articulações.', en: 'AI analyzes the model and automatically detects the best cut points — waist, neck, joints.' },
  suggested_cuts:    { pt: 'Cortes sugeridos pela IA', en: 'AI suggested cuts' },
  fine_adjust:       { pt: 'Ajuste fino da posição', en: 'Fine-tune position' },
  position:          { pt: 'Posição', en: 'Position' },
  no_cut_found:      { pt: 'Nenhum ponto de corte claro encontrado. Ajuste manualmente com o slider.', en: 'No clear cut point found. Adjust manually with the slider.' },
  axis_x:            { pt: 'Eixo X (lateral)', en: 'X axis (side)' },
  axis_y:            { pt: 'Eixo Y (profundidade)', en: 'Y axis (depth)' },
  axis_z:            { pt: 'Eixo Z (altura)', en: 'Z axis (height)' },
  analyzing:         { pt: 'Analisando modelo…', en: 'Analyzing model…' },
  applying_cut:      { pt: 'Aplicando corte…', en: 'Applying cut…' },

  // Paint tools
  sel_mode:          { pt: 'Modo de Seleção', en: 'Selection Mode' },
  paint_title:       { pt: 'Ferramenta de seleção', en: 'Selection tool' },
  paint_brush:       { pt: 'Pincel', en: 'Brush' },
  paint_brush_sub:   { pt: 'Clique e arraste', en: 'Click and drag' },
  paint_fill:        { pt: 'Conta-gotas', en: 'Flood fill' },
  paint_fill_sub:    { pt: 'Um clique preenche', en: 'One click fills' },
  paint_eraser:      { pt: 'Borracha', en: 'Eraser' },
  paint_eraser_sub:  { pt: 'Apaga a seleção', en: 'Erases selection' },
  brush_settings:    { pt: 'Configurações do Pincel', en: 'Brush Settings' },
  eraser_size:       { pt: 'Tamanho da Borracha', en: 'Eraser Size' },
  fill_sensitivity:  { pt: 'Sensibilidade do Conta-gotas', en: 'Flood Fill Sensitivity' },
  size_label:        { pt: 'Tamanho', en: 'Size' },
  paint_brush_size:  { pt: 'Tamanho do pincel', en: 'Brush size' },
  stop_angle:        { pt: 'Ângulo de parada', en: 'Stop angle' },
  angle_scale_lo:    { pt: '1° — só superfícies planas', en: '1° — flat surfaces only' },
  angle_scale_hi:    { pt: '45° — ignora arestas', en: '45° — ignores edges' },
  angle_hint_1:      { pt: 'Só superfícies quase planas — ideal para peças mecânicas', en: 'Only near-flat surfaces — ideal for mechanical parts' },
  angle_hint_2:      { pt: 'Padrão recomendado — para bem em dobras suaves sem vazar', en: 'Recommended default — stops at soft folds without leaking' },
  angle_hint_3:      { pt: 'Atravessa dobras moderadas — cuidado em modelos orgânicos', en: 'Crosses moderate folds — careful with organic models' },
  angle_hint_4:      { pt: 'Alto — pode vazar para partes adjacentes conectadas', en: 'High — may leak into connected adjacent parts' },
  angle_hint_5:      { pt: 'Muito alto — vai pintar regiões não intencionais', en: 'Very high — will paint unintended regions' },
  max_radius:        { pt: 'Raio máximo de expansão', en: 'Max expansion radius' },
  unlimited:         { pt: 'Ilimitado', en: 'Unlimited' },
  no_limit:          { pt: 'Sem limite', en: 'No limit' },
  radius_hint_0:     { pt: 'Expande até onde o ângulo permitir', en: 'Expands as far as the angle allows' },
  radius_hint_hi:    { pt: '{r} mm — clique na ponta do membro (mão/pé) para capturar o braço/perna inteiro', en: '{r} mm — click the limb tip (hand/foot) to capture the whole arm/leg' },
  radius_hint_lo:    { pt: 'Expande até {r} mm do clique — útil para isolar dedos ou peças pequenas', en: 'Expands up to {r} mm from the click — useful to isolate fingers or small parts' },
  paint_clear:       { pt: 'Limpar tudo', en: 'Clear all' },
  paint_undo:        { pt: 'Desfazer', en: 'Undo' },
  fill_gaps:         { pt: 'Preencher falhas', en: 'Fill gaps' },
  fill_gaps_tip:     { pt: 'Preenche triângulos ilhados dentro da seleção — evita buracos na malha', en: 'Fills isolated triangles inside the selection — avoids mesh holes' },
  undo_click_hint:   { pt: 'Ctrl+Z desfaz um clique por vez', en: 'Ctrl+Z undoes one click at a time' },
  how_works:         { pt: 'Como funciona', en: 'How it works' },
  hiw_paint_html:    { pt: 'Pinte as faces da <b> (vermelha, recebe as cavidades) — a área não pintada será a <a> (azul, recebe os pinos). Somente o que você pintar vira a Parte B.', en: 'Paint the faces of <b> (red, gets the cavities) — the unpainted area becomes <a> (blue, gets the pins). Only what you paint becomes Part B.' },
  hiw_fill:          { pt: 'Conta-gotas: um clique seleciona toda a região conectada. Ajuste o ângulo para controlar até onde expande.', en: 'Flood fill: one click selects the whole connected region. Adjust the angle to control expansion.' },
  hiw_brush:         { pt: 'Pincel: clique e arraste para pintar face a face.', en: 'Brush: click and drag to paint face by face.' },
  hiw_undo:          { pt: 'Ctrl+Z desfaz o último clique.', en: 'Ctrl+Z undoes the last click.' },
  paint_faces:       { pt: 'Faces pintadas', en: 'Painted faces' },
  detecting_region:  { pt: 'Detectando região…', en: 'Detecting region…' },

  // Preview
  preview_title:     { pt: 'Preview dos encaixes', en: 'Joint preview' },
  preview_hint:      { pt: 'Pinos machos (azul) serão adicionados à Parte A. Cavidades fêmeas (vermelho) serão subtraídas da Parte B.', en: 'Male pins (blue) will be added to Part A. Female cavities (red) will be subtracted from Part B.' },
  preview_analyze:   { pt: 'Analise a linha de corte no viewer e confirme para gerar o preview dos encaixes.', en: 'Check the cut line in the viewer and confirm to generate the joint preview.' },
  btn_gen_preview:   { pt: 'Gerar preview dos encaixes', en: 'Generate joint preview' },
  joint_params:      { pt: 'Parâmetros dos Encaixes', en: 'Joint Parameters' },
  total_pins:        { pt: 'Total de pinos', en: 'Total pins' },
  pin_diameter:      { pt: 'Diâmetro (macho)', en: 'Diameter (male)' },
  pin_depth:         { pt: 'Profundidade', en: 'Depth' },
  total_clearance:   { pt: 'Folga total', en: 'Total clearance' },
  legend:            { pt: 'Legenda', en: 'Legend' },
  preview_check:     { pt: 'Verifique a distribuição dos pinos no viewer. Se estiver correto, confirme para processar.', en: 'Check the pin distribution in the viewer. If correct, confirm to process.' },
  preview_confirm:   { pt: 'Confirmar e processar', en: 'Confirm and process' },
  preview_cancel:    { pt: 'Voltar e ajustar', en: 'Go back and adjust' },

  // Tipos de conector + assembly fit
  joint_type_label:  { pt: 'Tipo de conector', en: 'Connector type' },
  joint_pin:         { pt: 'Pino', en: 'Pin' },
  joint_ball:        { pt: 'Esfera', en: 'Ball' },
  joint_dovetail:    { pt: 'Dovetail', en: 'Dovetail' },
  joint_hint_pin:      { pt: 'Cilindro simples — conexão direta.', en: 'Simple cylinder — direct connection.' },
  joint_hint_ball:     { pt: 'Junta esférica — permite leve ajuste angular.', en: 'Ball joint — allows slight angular adjustment.' },
  joint_hint_dovetail: { pt: 'Plug afunilado — auto-centrante, resiste a deslizamento lateral.', en: 'Tapered plug — self-centering, resists lateral sliding.' },
  fit_label:         { pt: 'Encaixe (fit)', en: 'Assembly fit' },
  fit_flexivel:      { pt: 'Flexível', en: 'Flexible' },
  fit_apertado:      { pt: 'Apertado', en: 'Tight' },
  fit_hint_flexivel: { pt: 'Folga de 1mm por lado — montagem fácil, bom para pintura.', en: '1mm clearance per side — easy assembly, good for painting.' },
  fit_hint_apertado: { pt: 'Folga de 0,2mm por lado — encaixe justo por pressão.', en: '0.2mm clearance per side — tight press fit.' },
  show_xray:         { pt: 'Raio-X (folga)', en: 'X-Ray (clearance)' },

  // Edição individual por conector
  pin_editor:        { pt: 'Conector', en: 'Connector' },
  pin_editor_done:   { pt: 'Concluir', en: 'Done' },
  pin_editor_hint:   { pt: 'Clique num conector no viewer para editá-lo individualmente (tipo, tamanho, ângulo).', en: 'Click a connector in the viewer to edit it individually (type, size, angle).' },
  edit_diameter:     { pt: 'Diâmetro', en: 'Diameter' },
  edit_depth:        { pt: 'Profundidade', en: 'Depth' },
  edit_angle_u:      { pt: 'Inclinação A', en: 'Tilt A' },
  edit_angle_v:      { pt: 'Inclinação B', en: 'Tilt B' },

  // Add all connectors (multi-interface)
  btn_skip_joints:     { pt: 'Pular encaixes', en: 'Skip joints' },
  btn_add_all:         { pt: 'Adicionar conectores em todas', en: 'Add all connectors' },
  pending_interfaces:  { pt: 'interface(s) de corte sem conector.', en: 'cut interface(s) without connectors.' },

  // Modo Professional (§1 — máscara multi-peça)
  rp_multimask:        { pt: 'Modo Professional', en: 'Professional Mode' },
  btn_pro_mode:        { pt: 'Modo Professional (multi-peças)', en: 'Professional mode (multi-part)' },
  status_multimask:    { pt: 'Revisando máscara multi-peça', en: 'Reviewing multi-part mask' },
  proc_segmenting:     { pt: 'Segmentando o modelo…', en: 'Segmenting model…' },
  granularity_label:   { pt: 'Granularidade', en: 'Granularity' },
  gran_baixa:          { pt: 'Baixa', en: 'Low' },
  gran_media:          { pt: 'Média', en: 'Medium' },
  gran_alta:           { pt: 'Alta', en: 'High' },
  gran_hint:           { pt: 'Baixa = poucas peças grandes; alta = mais peças menores.', en: 'Low = few large pieces; high = more smaller pieces.' },
  regions_title:       { pt: 'Regiões detectadas', en: 'Detected regions' },
  region_label:        { pt: 'Região', en: 'Region' },
  mask_hint_select:    { pt: 'Clique numa região no modelo (ou na lista) para selecioná-la. Regiões viram peças separadas ao aplicar.', en: 'Click a region on the model (or in the list) to select it. Regions become separate pieces when applied.' },
  mask_one_region:     { pt: 'Só uma região foi detectada — aumente a granularidade ou use a seleção manual.', en: 'Only one region detected — increase granularity or use manual selection.' },
  btn_split_region:    { pt: 'Dividir região', en: 'Split region' },
  btn_apply_mask:      { pt: 'Aplicar máscara', en: 'Apply mask' },
  pieces_suffix:       { pt: 'peças', en: 'pieces' },

  // Processing
  processing:        { pt: 'Processando…', en: 'Processing…' },
  proc_cutting:      { pt: 'Dividindo a malha…', en: 'Splitting the mesh…' },
  proc_joints:       { pt: 'Gerando encaixes…', en: 'Generating joints…' },
  proc_closing:      { pt: 'Fechando bordas…', en: 'Closing edges…' },

  // Parts
  parts_title:       { pt: 'Partes', en: 'Parts' },
  parts_a:           { pt: 'Parte A (pinos machos)', en: 'Part A (male pins)' },
  parts_b:           { pt: 'Parte B (cavidades fêmeas)', en: 'Part B (female cavities)' },
  part_a_short:      { pt: 'Parte A', en: 'Part A' },
  part_b_short:      { pt: 'Parte B', en: 'Part B' },

  // Result
  cut_more:          { pt: 'Dividir mais uma parte', en: 'Split another part' },
  cut_more_hint:     { pt: 'Todas as partes cortadas até agora. Clique na tesoura para dividir qualquer uma novamente — as demais ficam salvas.', en: 'All parts cut so far. Click the scissors to split any of them again — the others stay saved.' },
  parts_all:         { pt: 'Partes do modelo', en: 'Model parts' },
  parts_done:        { pt: 'Partes prontas', en: 'Finished parts' },
  part_done_tag:     { pt: 'pronta', en: 'done' },
  faces_suffix:      { pt: 'faces', en: 'faces' },

  // View modes
  view_title:        { pt: 'Modo de Visualização', en: 'View Mode' },
  view_side:         { pt: 'Lado a lado', en: 'Side by side' },
  view_tabs:         { pt: 'Abas separadas', en: 'Separate tabs' },
  view_same:         { pt: 'Mesma tela', en: 'Same view' },
  overlays:          { pt: 'Sobreposições', en: 'Overlays' },
  view_wireframe:    { pt: 'Exibir wireframe', en: 'Show wireframe' },
  view_joints:       { pt: 'Exibir encaixes', en: 'Show joints' },

  // Export
  export_title:      { pt: 'Exportar', en: 'Export' },
  export_format:     { pt: 'Formato', en: 'Format' },
  export_part_a:     { pt: 'Baixar Parte A', en: 'Download Part A' },
  export_part_b:     { pt: 'Baixar Parte B', en: 'Download Part B' },
  export_zip:        { pt: 'Baixar ZIP (ambas)', en: 'Download ZIP (both)' },
  export_zip_all:    { pt: 'Baixar todas ({n} partes) ZIP', en: 'Download all ({n} parts) ZIP' },
  export_download:   { pt: 'Baixar', en: 'Download' },
  export_rename:     { pt: 'Nome do arquivo', en: 'File name' },

  // Buttons
  btn_next_paint:    { pt: 'Ir para pintura →', en: 'Go to paint →' },
  btn_preview:       { pt: 'Preview dos encaixes →', en: 'Preview joints →' },
  btn_next_step:     { pt: 'Próximo passo', en: 'Next step' },
  btn_reset:         { pt: 'Reiniciar', en: 'Reset' },
  btn_fit:           { pt: 'Enquadrar', en: 'Fit camera' },
  btn_open_new:      { pt: 'Abrir outro modelo', en: 'Open another model' },
  btn_detect_cuts:   { pt: 'Detectar cortes automáticos', en: 'Detect automatic cuts' },
  btn_manual_sel:    { pt: 'Seleção manual', en: 'Manual selection' },
  btn_import_other:  { pt: 'Importar outro', en: 'Import another' },
  btn_apply_cut:     { pt: 'Aplicar corte', en: 'Apply cut' },
  btn_back:          { pt: 'Voltar', en: 'Back' },
  btn_adjust_cut:    { pt: 'Ajustar corte', en: 'Adjust cut' },
  btn_import_new:    { pt: 'Importar novo modelo', en: 'Import new model' },

  // Viewer loading
  loading_geometry:  { pt: 'Baixando geometria…', en: 'Downloading geometry…' },
  processing_faces:  { pt: 'Processando {n} faces…', en: 'Processing {n} faces…' },
  loading_model:     { pt: 'Carregando modelo…', en: 'Loading model…' },
  loading_large:     { pt: 'Isso pode levar alguns segundos para modelos grandes', en: 'This may take a few seconds for large models' },

  // Errors / messages
  err_upload:        { pt: 'Erro ao carregar o arquivo.', en: 'Error loading file.' },
  err_paint:         { pt: 'Erro na seleção. Tente outro ponto ou ajuste o ângulo.', en: 'Selection error. Try another point or adjust the angle.' },
  err_smart:         { pt: 'Erro no Smart Select. Tente outro ponto.', en: 'Smart Select error. Try another point.' },
  err_generic:       { pt: 'Ocorreu um erro. Tente novamente.', en: 'An error occurred. Please try again.' },
  warn_no_faces:     { pt: 'Nenhuma face selecionada. Pinte a região desejada primeiro.', en: 'No faces selected. Paint the desired region first.' },
  heavy_title:       { pt: 'Modelo pesado', en: 'Heavy model' },
  heavy_msg:         { pt: 'Modelo com muitas faces. Operações podem demorar.', en: 'Model has many faces. Operations may take longer.' },

  // Session restore
  restore_title:     { pt: 'Retomar projeto', en: 'Resume project' },
  restore_msg:       { pt: 'Você tem uma sessão salva. Deseja continuar de onde parou?', en: 'You have a saved session. Continue where you left off?' },
  restore_yes:       { pt: 'Continuar sessão', en: 'Resume session' },
  restore_no:        { pt: 'Começar do zero', en: 'Start fresh' },
  restore_file:      { pt: 'Arquivo', en: 'File' },
  restore_expired:   { pt: 'Sessão expirada. Comece um novo projeto.', en: 'Session expired. Start a new project.' },

  // Toolbar / tooltips
  tooltip_wireframe: { pt: 'Wireframe (W)', en: 'Wireframe (W)' },
  tooltip_fit:       { pt: 'Enquadrar câmera (F)', en: 'Fit camera (F)' },
  tooltip_reset:     { pt: 'Resetar câmera', en: 'Reset camera' },

  // ── Página de planos ────────────────────────────────────────────────────
  header_plans:      { pt: 'Planos', en: 'Plans' },
  plans_back:        { pt: '← Voltar ao app', en: '← Back to app' },
  plans_title:       { pt: 'Escolha o plano ideal para as suas impressões', en: 'Choose the right plan for your prints' },
  plans_subtitle:    { pt: 'Fatie, encaixe e exporte modelos 3D sem complicação. Cancele quando quiser.', en: 'Slice, joint and export 3D models without hassle. Cancel anytime.' },
  plans_hero_badge:  { pt: '7 dias grátis no Pro — sem cartão de crédito', en: '7-day free Pro trial — no credit card' },
  plans_monthly:     { pt: 'Mensal', en: 'Monthly' },
  plans_annual:      { pt: 'Anual', en: 'Annual' },
  plans_save_pill:   { pt: 'Economize 25% — quase 3 meses grátis', en: 'Save 25% — almost 3 months free' },
  plans_annual_tag:  { pt: '-25%', en: '-25%' },
  plans_popular:     { pt: 'Popular', en: 'Popular' },
  plans_per_month:   { pt: '/mês', en: '/mo' },
  plans_billed_once: { pt: 'cobrado à vista no plano anual', en: 'billed upfront on the annual plan' },
  plans_equiv:       { pt: 'equivale a {v}/mês', en: 'works out to {v}/mo' },
  plans_cta:         { pt: 'Começar agora', en: 'Start now' },
  plans_cta_trial:   { pt: 'Testar grátis por 7 dias', en: 'Try free for 7 days' },
  plans_no_card:     { pt: 'sem cartão de crédito', en: 'no credit card required' },
  plan_essencial_name: { pt: 'Essencial', en: 'Essential' },
  plan_essencial_desc: { pt: 'Para makers que fatiam de vez em quando.', en: 'For makers who slice now and then.' },
  plan_pro_name:       { pt: 'Pro', en: 'Pro' },
  plan_pro_desc:       { pt: 'Fatiamento ilimitado para quem produz todo dia.', en: 'Unlimited slicing for everyday production.' },

  // Features (cards + tabela comparativa)
  feat_slices:       { pt: 'Fatiamentos por mês', en: 'Slices per month' },
  feat_slicing:      { pt: 'Fatiamento de modelos', en: 'Model slicing' },
  feat_formats:      { pt: 'Formatos STL, OBJ, 3MF', en: 'STL, OBJ, 3MF formats' },
  feat_gcode:        { pt: 'Exportação G-code', en: 'G-code export' },
  feat_updates:      { pt: 'Atualizações automáticas', en: 'Automatic updates' },
  feat_profiles:     { pt: 'Perfis de impressora', en: 'Printer profiles' },
  feat_history:      { pt: 'Histórico de projetos', en: 'Project history' },
  feat_extruders:    { pt: 'Múltiplos extrusores', en: 'Multiple extruders' },
  feat_batch:        { pt: 'Exportação em lote (batch)', en: 'Batch export' },
  feat_api:          { pt: 'API de integração', en: 'Integration API' },
  feat_cost:         { pt: 'Relatório de custo', en: 'Cost report' },
  feat_support:      { pt: 'Suporte', en: 'Support' },
  feat_early:        { pt: 'Acesso antecipado', en: 'Early access' },

  // Chips de limite
  chip_25mo:         { pt: 'até 25/mês', en: 'up to 25/mo' },
  chip_unlimited:    { pt: '∞ ilimitado', en: '∞ unlimited' },
  chip_upto3:        { pt: 'até 3', en: 'up to 3' },
  chip_30d:          { pt: '30 dias', en: '30 days' },
  chip_beta:         { pt: 'Beta', en: 'Beta' },
  chip_email:        { pt: 'E-mail', en: 'E-mail' },
  chip_chat:         { pt: 'Chat prioritário', en: 'Priority chat' },

  // Tabela comparativa
  plans_table_title:    { pt: 'Compare os planos', en: 'Compare plans' },
  plans_table_resource: { pt: 'Recurso', en: 'Feature' },
  plans_table_price:    { pt: 'Preço', en: 'Price' },
  plans_table_annual_note: { pt: '{v} à vista', en: '{v} upfront' },

  // FAQ
  plans_faq_title:   { pt: 'Perguntas frequentes', en: 'Frequently asked questions' },
  faq_limit_q:       { pt: 'Como funciona o limite de 25 fatiamentos do Essencial?', en: 'How does the Essential 25-slice limit work?' },
  faq_limit_a:       { pt: 'No plano Essencial você pode fatiar até 25 arquivos por mês — o contador zera no primeiro dia de cada ciclo de cobrança. Seus projetos e exportações anteriores continuam acessíveis mesmo com o limite atingido. Precisa de mais? No Pro o fatiamento é ilimitado, e o upgrade vale na hora com cobrança proporcional.', en: 'On the Essential plan you can slice up to 25 files per month — the counter resets on the first day of each billing cycle. Your previous projects and exports remain accessible even after hitting the limit. Need more? Pro has unlimited slicing, and upgrades apply instantly with pro-rated billing.' },
  faq_trial_q:       { pt: 'Como funciona o teste grátis de 7 dias?', en: 'How does the 7-day free trial work?' },
  faq_trial_a:       { pt: 'Todo usuário novo tem 7 dias de Pro completo sem precisar cadastrar cartão. Ao final do período, você escolhe um plano para continuar — nada é cobrado automaticamente.', en: 'Every new user gets 7 days of full Pro without registering a card. At the end of the period you pick a plan to continue — nothing is charged automatically.' },
  faq_change_q:      { pt: 'Posso mudar de plano depois?', en: 'Can I change plans later?' },
  faq_change_a:      { pt: 'Sim. Upgrade e downgrade estão disponíveis a qualquer momento, com cálculo proporcional: você só paga (ou recebe de volta) a diferença pelo tempo restante do ciclo.', en: 'Yes. Upgrades and downgrades are available at any time with pro-rated billing: you only pay (or get back) the difference for the remaining cycle.' },
  faq_cancel_annual_q: { pt: 'Posso cancelar o plano anual?', en: 'Can I cancel the annual plan?' },
  faq_cancel_annual_a: { pt: 'Pode. Nos primeiros 30 dias o cancelamento do plano anual tem reembolso proporcional ao período não utilizado. Depois disso, o acesso continua até o fim do período já pago.', en: 'Yes. Within the first 30 days, cancelling the annual plan gives a refund proportional to the unused period. After that, access continues until the end of the paid period.' },
  faq_projects_q:    { pt: 'O que acontece com meus projetos se eu cancelar?', en: 'What happens to my projects if I cancel?' },
  faq_projects_a:    { pt: 'Após o cancelamento, seus projetos ficam disponíveis por 30 dias em modo leitura — tempo de sobra para baixar tudo o que precisar.', en: 'After cancellation, your projects stay available for 30 days in read-only mode — plenty of time to download everything you need.' },
  faq_payment_q:     { pt: 'Quais formas de pagamento são aceitas?', en: 'Which payment methods are accepted?' },
  faq_payment_a:     { pt: 'Cartão de crédito (Visa, Mastercard e Elo) em todos os planos. PIX e boleto estão disponíveis apenas no plano anual, por ser uma cobrança única à vista.', en: 'Credit card (Visa, Mastercard and Elo) on all plans. PIX and boleto are available only on the annual plan, as it is a single upfront charge.' },

  // Checkout
  co_title:          { pt: 'Finalizar assinatura', en: 'Complete your subscription' },
  co_back:           { pt: '← Voltar aos planos', en: '← Back to plans' },
  co_summary:        { pt: 'Resumo do pedido', en: 'Order summary' },
  co_plan:           { pt: 'Plano', en: 'Plan' },
  co_period:         { pt: 'Cobrança', en: 'Billing' },
  co_period_mensal:  { pt: 'Mensal', en: 'Monthly' },
  co_period_anual:   { pt: 'Anual (à vista)', en: 'Annual (upfront)' },
  co_total:          { pt: 'Total hoje', en: 'Total today' },
  co_trial_note:     { pt: 'Novos usuários têm 7 dias grátis no Pro — a cobrança só acontece depois do teste.', en: 'New users get 7 free days of Pro — you are only charged after the trial.' },
  co_pay_title:      { pt: 'Forma de pagamento', en: 'Payment method' },
  co_pay_card:       { pt: 'Cartão de crédito', en: 'Credit card' },
  co_pay_card_sub:   { pt: 'Visa, Mastercard, Elo', en: 'Visa, Mastercard, Elo' },
  co_pay_pix:        { pt: 'PIX', en: 'PIX' },
  co_pay_boleto:     { pt: 'Boleto', en: 'Boleto' },
  co_pay_annual_only:{ pt: 'apenas no plano anual', en: 'annual plan only' },
  co_pay_btn:        { pt: 'Continuar para pagamento', en: 'Continue to payment' },
  co_gateway_note:   { pt: 'Integração com o gateway de pagamento em desenvolvimento — em breve você poderá concluir a assinatura por aqui.', en: 'Payment gateway integration under development — soon you will be able to complete your subscription here.' },
  co_refund_note:    { pt: 'Plano anual: reembolso proporcional nos primeiros 30 dias.', en: 'Annual plan: proportional refund within the first 30 days.' },

  // ── Login / registro ──────────────────────────────────────────────────────
  login_title:       { pt: 'Entre na sua conta', en: 'Sign in to your account' },
  login_subtitle:    { pt: 'Fatie, encaixe e exporte modelos 3D para impressão.', en: 'Slice, joint and export 3D models for printing.' },
  login_tab_signin:  { pt: 'Entrar', en: 'Sign in' },
  login_tab_signup:  { pt: 'Criar conta', en: 'Create account' },
  login_email:       { pt: 'E-mail', en: 'E-mail' },
  login_password:    { pt: 'Senha', en: 'Password' },
  login_name:        { pt: 'Nome (opcional)', en: 'Name (optional)' },
  login_btn:         { pt: 'Entrar', en: 'Sign in' },
  signup_btn:        { pt: 'Criar conta e começar', en: 'Create account and start' },
  signup_trial_note: { pt: '✦ Ao criar a conta você ganha 7 dias de Pro grátis — sem cartão.', en: '✦ Creating an account gives you 7 free days of Pro — no card needed.' },
  login_loading:     { pt: 'Entrando…', en: 'Signing in…' },
  err_login:         { pt: 'E-mail ou senha incorretos.', en: 'Wrong e-mail or password.' },
  err_email_taken:   { pt: 'Este e-mail já está cadastrado. Faça login.', en: 'This e-mail is already registered. Please sign in.' },
  err_email_invalid: { pt: 'Digite um e-mail válido.', en: 'Enter a valid e-mail.' },
  err_password_short:{ pt: 'A senha precisa de pelo menos 6 caracteres.', en: 'Password must be at least 6 characters.' },

  // ── Header / conta ────────────────────────────────────────────────────────
  header_account:    { pt: 'Minha conta', en: 'My account' },
  logout_btn:        { pt: 'Sair', en: 'Sign out' },
  acct_title:        { pt: 'Minha conta', en: 'My account' },
  acct_plan:         { pt: 'Plano atual', en: 'Current plan' },
  acct_status:       { pt: 'Status', en: 'Status' },
  acct_st_trialing:  { pt: 'Teste grátis (Pro)', en: 'Free trial (Pro)' },
  acct_st_active:    { pt: 'Ativa', en: 'Active' },
  acct_st_canceled:  { pt: 'Cancelada', en: 'Canceled' },
  acct_st_expired:   { pt: 'Expirada', en: 'Expired' },
  acct_trial_until:  { pt: 'Teste termina em', en: 'Trial ends on' },
  acct_next_billing: { pt: 'Acesso/renovação até', en: 'Access/renewal until' },
  acct_usage:        { pt: 'Fatiamentos neste mês', en: 'Slices this month' },
  acct_usage_unlim:  { pt: 'ilimitado', en: 'unlimited' },
  acct_upgrade:      { pt: 'Mudar de plano', en: 'Change plan' },
  acct_cancel:       { pt: 'Cancelar assinatura', en: 'Cancel subscription' },
  acct_cancel_confirm: { pt: 'Cancelar mesmo? O acesso segue até o fim do período pago; anual tem reembolso proporcional nos primeiros 30 dias.', en: 'Really cancel? Access continues until the end of the paid period; annual gets a proportional refund within the first 30 days.' },
  acct_canceled_ok:  { pt: 'Assinatura cancelada.', en: 'Subscription canceled.' },
  acct_refund:       { pt: 'Reembolso proporcional', en: 'Proportional refund' },
  acct_back_app:     { pt: '← Voltar ao app', en: '← Back to app' },

  // ── Paywall ───────────────────────────────────────────────────────────────
  paywall_notice:    { pt: 'Seu período de teste terminou — escolha um plano para continuar fatiando.', en: 'Your trial has ended — pick a plan to keep slicing.' },
  paywall_logged_as: { pt: 'Conectado como', en: 'Signed in as' },
  quota_reached:     { pt: 'Você atingiu os 25 fatiamentos do plano Essencial neste mês. Faça upgrade para o Pro para continuar sem limites.', en: 'You reached the 25 slices of the Essential plan this month. Upgrade to Pro to continue without limits.' },
  sub_required:      { pt: 'Assinatura necessária para fatiar. Escolha um plano.', en: 'A subscription is required to slice. Pick a plan.' },
}

let _lang = localStorage.getItem('zs_lang') || 'pt'

export function getLang() { return _lang }

export function setLang(l) {
  _lang = l
  localStorage.setItem('zs_lang', l)
}

export function t(key) {
  const entry = STRINGS[key]
  if (!entry) return key
  return entry[_lang] || entry['pt'] || key
}

// t() com placeholders: tf('processing_faces', { n: 1200 })
export function tf(key, vars = {}) {
  let s = t(key)
  for (const [k, v] of Object.entries(vars)) {
    s = s.replaceAll(`{${k}}`, String(v))
  }
  return s
}
