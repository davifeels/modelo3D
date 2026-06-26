import numpy as np

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QListWidget,
    QListWidgetItem, QButtonGroup, QRadioButton, QDoubleSpinBox,
    QSpinBox, QFileDialog, QMessageBox, QSplitter, QStatusBar,
    QInputDialog, QApplication,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from ui.viewer_widget import ViewerWidget
from src.importer import load_mesh, HEAVY_MESH_THRESHOLD, SIMPLIFY_TARGET
from src.cutter import (
    cut_mesh, get_cross_section_points,
    split_by_components, simplify_mesh, AXIS_NORMALS, AXIS_IDX,
    region_grow_and_cut, find_interface, find_adjacent_part,
)
from src.joints import add_joints, JointParams
from src.exporter import export_parts, export_single_part


class _Worker(QThread):
    done = pyqtSignal(object, str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.done.emit(result, "")
        except Exception as e:
            self.done.emit(None, str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZefiroSplit")
        self.resize(1400, 900)

        self._original_parts: list = []
        self._original_names: list = []
        self._parts: list = []
        self._part_names: list = []
        self._joint_info: dict = {}       # (nome_a, nome_b) → (eixo, posição)
        self._history: list = []
        self._selected_idx: int = 0
        self._pick_mode: bool = False
        self._wireframe: bool = False
        self._exploded: bool = False
        self._explode_factor: float = 2.5
        self._worker = None

        self._build_ui()

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_panel())
        self.viewer = ViewerWidget(self)
        splitter.addWidget(self.viewer)
        splitter.setSizes([340, 1060])
        self.setCentralWidget(splitter)

        bar = self.menuBar()
        fm = bar.addMenu("Arquivo")
        fm.addAction("Abrir STL / OBJ...", self._open_file)
        fm.addSeparator()
        fm.addAction("Exportar partes como ZIP...", self._export)
        fm.addAction("Exportar parte selecionada...", self._export_single)
        fm.addSeparator()
        fm.addAction("Sair", self.close)
        vm = bar.addMenu("Visualizar")
        vm.addAction("Alternar Wireframe\tW", self._toggle_wireframe)
        vm.addAction("Vista explodida\tE", self._toggle_exploded)
        vm.addAction("Enquadrar câmera\tF", lambda: self.viewer.fit_view())
        hm = bar.addMenu("Ajuda")
        hm.addAction("Sobre", self._about)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Pronto. Abra um arquivo STL ou OBJ para começar.")

    def _build_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(340)
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(8, 8, 8, 8)

        btn_open = QPushButton("Abrir STL / OBJ")
        btn_open.setFixedHeight(40)
        btn_open.setStyleSheet(
            "QPushButton{background:#1565C0;color:white;font-weight:bold;font-size:13px;border-radius:5px;}"
            "QPushButton:hover{background:#1976D2;}")
        btn_open.clicked.connect(self._open_file)
        lay.addWidget(btn_open)

        lay.addWidget(self._build_info_group())
        lay.addWidget(self._build_paint_group())
        lay.addWidget(self._build_cut_group())
        lay.addWidget(self._build_joint_group())
        lay.addWidget(self._build_parts_group())

        row_exp = QHBoxLayout()
        btn_exp = QPushButton("Exportar ZIP")
        btn_exp.setFixedHeight(38)
        btn_exp.setStyleSheet(
            "QPushButton{background:#2E7D32;color:white;font-weight:bold;font-size:12px;border-radius:5px;}"
            "QPushButton:hover{background:#388E3C;}")
        btn_exp.clicked.connect(self._export)
        btn_exp1 = QPushButton("Exportar Parte")
        btn_exp1.setFixedHeight(38)
        btn_exp1.setToolTip("Exporta somente a parte selecionada (STL ou OBJ)")
        btn_exp1.setStyleSheet(
            "QPushButton{background:#1B5E20;color:white;font-size:11px;border-radius:5px;}"
            "QPushButton:hover{background:#2E7D32;}")
        btn_exp1.clicked.connect(self._export_single)
        row_exp.addWidget(btn_exp)
        row_exp.addWidget(btn_exp1)
        lay.addLayout(row_exp)

        lay.addStretch()
        return w

    def _build_info_group(self) -> QGroupBox:
        grp = QGroupBox("Informações do modelo")
        lay = QVBoxLayout(grp)
        lay.setSpacing(3)
        self._lbl_name = QLabel("—")
        self._lbl_name.setStyleSheet("font-weight:bold;")
        self._lbl_verts = QLabel("Vértices: —")
        self._lbl_faces = QLabel("Faces: —")
        self._lbl_dims = QLabel("Dims: —")
        self._lbl_unit = QLabel("Unidade: —")
        self._lbl_wt = QLabel("Watertight: —")
        self._lbl_comp = QLabel("Componentes: —")
        self._lbl_comp.setStyleSheet("color:#4FC3F7;font-weight:bold;")
        for lbl in [self._lbl_name, self._lbl_verts, self._lbl_faces,
                    self._lbl_dims, self._lbl_unit, self._lbl_wt, self._lbl_comp]:
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        return grp

    def _build_paint_group(self) -> QGroupBox:
        """Grupo de pintura automática com IA (region growing)."""
        grp = QGroupBox("Pintar e Separar  (IA)")
        lay = QVBoxLayout(grp)
        lay.setSpacing(4)

        info = QLabel(
            "Clique em uma parte do modelo para selecioná-la.\n"
            "A IA detecta os limites automaticamente."
        )
        info.setStyleSheet("color:#90CAF9;font-size:10px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        self._btn_pick = QPushButton("Pintar Parte  (clique na mesh)")
        self._btn_pick.setCheckable(True)
        self._btn_pick.setFixedHeight(34)
        self._btn_pick.setStyleSheet(
            "QPushButton{background:#4527A0;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:checked{background:#7C4DFF;}"
            "QPushButton:hover{background:#512DA8;}")
        self._btn_pick.toggled.connect(self._toggle_pick_mode)
        lay.addWidget(self._btn_pick)

        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel("Ângulo limite:"))
        self._spin_grow_angle = QDoubleSpinBox()
        self._spin_grow_angle.setRange(5.0, 90.0)
        self._spin_grow_angle.setValue(30.0)
        self._spin_grow_angle.setDecimals(0)
        self._spin_grow_angle.setSuffix("°")
        self._spin_grow_angle.setToolTip(
            "Ângulo de parada da pintura.\n"
            "30° = padrão (detecta bordas nítidas).\n"
            "Reduza para selecionar regiões menores (ex: olho).\n"
            "Aumente se a seleção parar cedo demais."
        )
        angle_row.addWidget(self._spin_grow_angle)
        lay.addLayout(angle_row)

        self._btn_auto_join = QPushButton("Separar + Encaixar Auto")
        self._btn_auto_join.setFixedHeight(34)
        self._btn_auto_join.setStyleSheet(
            "QPushButton{background:#6A1B9A;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#7B1FA2;}")
        self._btn_auto_join.setToolTip(
            "Gera encaixe automático entre a parte selecionada\n"
            "e o componente adjacente mais próximo."
        )
        self._btn_auto_join.clicked.connect(self._auto_join_with_adjacent_selected)
        lay.addWidget(self._btn_auto_join)

        return grp

    def _build_cut_group(self) -> QGroupBox:
        grp = QGroupBox("Corte por plano  (manual)")
        lay = QVBoxLayout(grp)
        lay.setSpacing(4)

        ax_row = QHBoxLayout()
        ax_row.addWidget(QLabel("Eixo:"))
        self._axis_grp = QButtonGroup(self)
        for label in ("X", "Y", "Z"):
            rb = QRadioButton(label)
            if label == "Z":
                rb.setChecked(True)
            self._axis_grp.addButton(rb)
            ax_row.addWidget(rb)
            rb.toggled.connect(self._on_axis_changed)
        lay.addLayout(ax_row)

        lay.addWidget(QLabel("Posição:"))
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.setValue(500)
        self._slider.valueChanged.connect(self._on_slider_changed)
        lay.addWidget(self._slider)
        self._lbl_pos = QLabel("Posição: —")
        lay.addWidget(self._lbl_pos)

        self._btn_wire = QPushButton("Wireframe  [W]")
        self._btn_wire.setCheckable(True)
        self._btn_wire.setStyleSheet(
            "QPushButton{background:#37474F;color:white;border-radius:4px;}"
            "QPushButton:checked{background:#546E7A;}"
            "QPushButton:hover{background:#455A64;}")
        self._btn_wire.toggled.connect(self._set_wireframe)
        lay.addWidget(self._btn_wire)

        row_cut = QHBoxLayout()
        btn_cut = QPushButton("Aplicar Corte")
        btn_cut.setStyleSheet(
            "QPushButton{background:#0277BD;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#0288D1;}")
        btn_cut.clicked.connect(self._apply_cut)
        btn_split = QPushButton("Separar Componentes")
        btn_split.setToolTip("Divide a parte selecionada nos seus corpos separados")
        btn_split.setStyleSheet(
            "QPushButton{background:#00695C;color:white;border-radius:4px;}"
            "QPushButton:hover{background:#00796B;}")
        btn_split.clicked.connect(self._apply_component_split)
        row_cut.addWidget(btn_cut)
        row_cut.addWidget(btn_split)
        lay.addLayout(row_cut)

        return grp

    def _build_joint_group(self) -> QGroupBox:
        grp = QGroupBox("Parâmetros do encaixe")
        lay = QVBoxLayout(grp)
        lay.setSpacing(4)

        def spin_row(label, val, mn, mx, dec, suffix):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            if dec == 0:
                sb = QSpinBox()
                sb.setRange(int(mn), int(mx))
                sb.setValue(int(val))
                sb.setSuffix(suffix)
            else:
                sb = QDoubleSpinBox()
                sb.setRange(mn, mx)
                sb.setValue(val)
                sb.setDecimals(dec)
                sb.setSuffix(suffix)
            row.addWidget(sb)
            lay.addLayout(row)
            return sb

        self._spin_diam = spin_row("Diâm. pino:", 3.0, 1.0, 20.0, 1, " mm")
        self._spin_depth = spin_row("Prof. pino:", 8.0, 2.0, 50.0, 1, " mm")
        self._spin_tol = spin_row("Tolerância:", 0.2, 0.0, 2.0, 2, " mm")
        self._spin_pins = spin_row("Qtd. pinos:", 1, 1, 6, 0, "")

        btn_joint = QPushButton("Adicionar Encaixe à Parte Selecionada")
        btn_joint.setStyleSheet(
            "QPushButton{background:#4A148C;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#6A1B9A;}")
        btn_joint.clicked.connect(self._apply_joints)
        lay.addWidget(btn_joint)

        return grp

    def _build_parts_group(self) -> QGroupBox:
        grp = QGroupBox("Partes  (duplo-clique para renomear)")
        lay = QVBoxLayout(grp)

        self._parts_list = QListWidget()
        self._parts_list.setMaximumHeight(150)
        self._parts_list.currentRowChanged.connect(self._on_part_selected)
        self._parts_list.itemDoubleClicked.connect(self._rename_part)
        lay.addWidget(self._parts_list)

        row1 = QHBoxLayout()
        btn_undo = QPushButton("Desfazer")
        btn_undo.clicked.connect(self._undo)
        btn_reset = QPushButton("Resetar")
        btn_reset.clicked.connect(self._reset)
        btn_fit = QPushButton("Enquadrar")
        btn_fit.clicked.connect(lambda: self.viewer.fit_view())
        row1.addWidget(btn_undo)
        row1.addWidget(btn_reset)
        row1.addWidget(btn_fit)
        lay.addLayout(row1)

        # Vista explodida — visualiza peças separadas como vão ficar na impressão
        self._btn_explode = QPushButton("Vista Explodida  [E]")
        self._btn_explode.setCheckable(True)
        self._btn_explode.setToolTip(
            "Afasta as peças para visualizar como vão ficar\n"
            "separadas na impressora 3D."
        )
        self._btn_explode.setStyleSheet(
            "QPushButton{background:#263238;color:white;border-radius:4px;}"
            "QPushButton:checked{background:#E65100;color:white;font-weight:bold;}"
            "QPushButton:hover{background:#37474F;}")
        self._btn_explode.toggled.connect(self._toggle_exploded_btn)
        lay.addWidget(self._btn_explode)

        return grp

    # ── Helpers de estado ─────────────────────────────────────────────────────

    def _current_axis(self) -> str:
        for btn in self._axis_grp.buttons():
            if btn.isChecked():
                return btn.text().lower()
        return "z"

    def _current_position(self) -> float:
        if not self._parts:
            return 0.0
        idx = min(self._selected_idx, len(self._parts) - 1)
        mesh = self._parts[idx]
        ax = self._current_axis()
        ai = AXIS_IDX[ax]
        lo = mesh.bounds[0][ai]
        hi = mesh.bounds[1][ai]
        return lo + (self._slider.value() / 1000.0) * (hi - lo)

    def _refresh_cut_plane(self):
        if not self._parts or self._exploded:
            self.viewer.hide_cut_plane()
            return
        idx = min(self._selected_idx, len(self._parts) - 1)
        pos = self._current_position()
        self._lbl_pos.setText(f"Posição: {pos:.2f} mm")
        self.viewer.show_cut_plane(self._parts[idx].bounds, self._current_axis(), pos)

    def _refresh_parts_list(self):
        self._parts_list.blockSignals(True)
        self._parts_list.clear()
        for name in self._part_names:
            self._parts_list.addItem(QListWidgetItem(name))
        if self._parts_list.count() > 0:
            row = min(self._selected_idx, self._parts_list.count() - 1)
            self._parts_list.setCurrentRow(row)
        self._parts_list.blockSignals(False)

    def _refresh_viewer(self):
        if self._exploded and len(self._parts) > 1:
            self.viewer.show_exploded(
                self._parts, self._part_names,
                self._explode_factor, self._selected_idx
            )
            self.viewer.hide_cut_plane()
        else:
            self.viewer.show_parts(self._parts, self._part_names, self._selected_idx)
            self._refresh_cut_plane()

    def _set_busy(self, msg: str):
        self._status.showMessage(f"⏳  {msg}")
        self.setEnabled(False)

    def _set_ready(self, msg: str):
        self._status.showMessage(msg)
        self.setEnabled(True)

    def _save_state(self):
        self._history.append((
            [p.copy() for p in self._parts],
            self._part_names[:],
            dict(self._joint_info),
            self._selected_idx,
        ))
        if len(self._history) > 8:
            self._history.pop(0)

    def _joint_params(self) -> JointParams:
        return JointParams(
            pin_diameter=self._spin_diam.value(),
            pin_depth=self._spin_depth.value(),
            tolerance=self._spin_tol.value(),
            n_pins=self._spin_pins.value(),
        )

    # ── Eventos ───────────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        focused = QApplication.focusWidget()
        is_text_input = isinstance(focused, (QSpinBox, QDoubleSpinBox))
        if not is_text_input:
            if event.key() == Qt.Key_W:
                self._btn_wire.setChecked(not self._btn_wire.isChecked())
                return
            if event.key() == Qt.Key_E:
                self._btn_explode.setChecked(not self._btn_explode.isChecked())
                return
            if event.key() == Qt.Key_F:
                self.viewer.fit_view()
                return
        super().keyPressEvent(event)

    def _on_axis_changed(self):
        self._refresh_cut_plane()

    def _on_slider_changed(self):
        self._refresh_cut_plane()

    def _on_part_selected(self, row: int):
        if row >= 0:
            self._selected_idx = row
            self._refresh_cut_plane()
            self.viewer.show_parts(self._parts, self._part_names, self._selected_idx)

    def _toggle_pick_mode(self, checked: bool):
        self._pick_mode = checked
        if checked:
            self.viewer.enable_picking(self._on_mesh_picked)
            n = len(self._parts)
            if n == 1:
                self._status.showMessage(
                    "IA ativa — clique na parte que deseja separar. "
                    f"Ângulo limite: {self._spin_grow_angle.value():.0f}°"
                )
            else:
                self._status.showMessage(
                    f"IA ativa — clique na parte desejada ({n} componentes detectados)."
                )
        else:
            self.viewer.deactivate_picking()
            self._status.showMessage("Modo de pintura desativado.")

    def _toggle_wireframe(self):
        self._btn_wire.setChecked(not self._btn_wire.isChecked())

    def _set_wireframe(self, enabled: bool):
        self._wireframe = enabled
        self.viewer._wireframe = enabled
        if self._parts:
            self._refresh_viewer()

    def _toggle_exploded(self):
        self._btn_explode.setChecked(not self._btn_explode.isChecked())

    def _toggle_exploded_btn(self, checked: bool):
        self._exploded = checked
        if self._parts:
            self._refresh_viewer()
            if checked:
                self.viewer.fit_view()
                self._status.showMessage(
                    f"Vista explodida — {len(self._parts)} peça(s) separadas para visualização. "
                    "Tecla E para fechar."
                )
            else:
                self._status.showMessage("Vista normal.")

    # ── Pintura / seleção de componente ──────────────────────────────────────

    def _on_mesh_picked(self, point: np.ndarray):
        """Callback do modo pintura: seleciona componente ou faz region growing."""
        if not self._parts:
            return

        if len(self._parts) == 1:
            # Modelo sólido: region growing a partir do ponto clicado
            self._btn_pick.setChecked(False)
            mesh = self._parts[0]
            base_name = self._part_names[0]
            angle = float(self._spin_grow_angle.value())

            self._set_busy(f"IA detectando região (ângulo {angle:.0f}°)...")

            worker = _Worker(region_grow_and_cut, mesh, point, angle)
            self._worker = worker

            def on_grown(result, err):
                if err:
                    self._set_ready("Erro na detecção de região.")
                    QMessageBox.warning(
                        self, "Erro na pintura",
                        f"{err}\n\nDicas:\n"
                        "• Tente clicar mais próximo do centro da parte desejada\n"
                        "• Ajuste o ângulo limite (menor = bordas mais nítidas)\n"
                        "• 30° = padrão  |  15° = bordas finas  |  45° = regiões largas"
                    )
                    return

                part_painted, part_base, cut_origin, cut_normal = result
                total = len(part_painted.faces) + len(part_base.faces)
                pct = len(part_painted.faces) / total * 100
                wt_p = part_painted.is_watertight
                wt_b = part_base.is_watertight

                reply = QMessageBox.question(
                    self, "Região detectada pela IA",
                    f"Parte pintada: {len(part_painted.faces):,} faces  ({pct:.0f}%)"
                    f"  {'✓ fechada' if wt_p else '⚠ aberta'}\n"
                    f"Base: {len(part_base.faces):,} faces  ({100-pct:.0f}%)"
                    f"  {'✓ fechada' if wt_b else '⚠ aberta'}\n\n"
                    "Deseja separar e gerar encaixe automático?\n\n"
                    "(Se a seleção ficou errada, clique Não, ajuste o ângulo e tente novamente.)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )

                if reply == QMessageBox.No:
                    self._set_ready("Seleção cancelada. Ajuste o ângulo e tente novamente.")
                    return

                name_painted = f"{base_name}_pintado"
                name_rest = f"{base_name}_base"

                self._save_state()
                self._parts = [part_painted, part_base]
                self._part_names = [name_painted, name_rest]
                self._joint_info = {}
                self._selected_idx = 0
                self._refresh_parts_list()
                self._refresh_viewer()
                self._set_ready(f"Dividido: '{name_painted}' + '{name_rest}'. Gerando encaixe...")

                # Usa o plano exato detectado pela IA para posicionar o encaixe
                self._auto_join_with_plane(0, cut_origin, cut_normal)

            worker.done.connect(on_grown)
            worker.start()

        else:
            # Modelo com múltiplos componentes: seleciona por proximidade
            from scipy.spatial import cKDTree
            min_dist = float("inf")
            best_idx = 0
            for i, mesh in enumerate(self._parts):
                verts = np.asarray(mesh.vertices, dtype=float)
                step = max(1, len(verts) // 3000)
                sample = verts[::step]
                tree = cKDTree(sample)
                d, _ = tree.query(point)
                if float(d) < min_dist:
                    min_dist = float(d)
                    best_idx = i

            self._selected_idx = best_idx
            self._parts_list.setCurrentRow(best_idx)
            self.viewer.show_parts(self._parts, self._part_names, best_idx)
            name = self._part_names[best_idx]
            self._status.showMessage(
                f"Selecionado: '{name}'  —  clique 'Separar + Encaixar Auto' para gerar o encaixe"
            )

    # ── Encaixe automático ────────────────────────────────────────────────────

    def _auto_join_with_adjacent_selected(self):
        """Botão 'Separar + Encaixar Auto' — usa a parte selecionada na lista."""
        if not self._parts:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return
        if len(self._parts) < 2:
            QMessageBox.warning(
                self, "Aviso",
                "Só há uma parte no modelo.\n\n"
                "Use 'Pintar Parte' para selecionar uma região,\n"
                "ou 'Separar Componentes' se o modelo tiver partes separadas."
            )
            return
        self._auto_join_with_adjacent(min(self._selected_idx, len(self._parts) - 1))

    def _auto_join_with_adjacent(self, idx: int):
        """
        Encontra o componente adjacente ao idx, detecta a interface,
        e adiciona encaixe automático macho/fêmea.
        """
        selected = self._parts[idx]
        selected_name = self._part_names[idx]

        other_indices = [i for i in range(len(self._parts)) if i != idx]
        other_parts = [self._parts[i] for i in other_indices]

        params = self._joint_params()

        self._set_busy(f"Detectando encaixe para '{selected_name}'...")

        def do_auto_join():
            adj_rel = find_adjacent_part(selected, other_parts)
            adjacent = other_parts[adj_rel]
            origin, normal = find_interface(selected, adjacent)
            section_pts = np.array([origin])
            new_sel, new_adj, warnings = add_joints(
                selected, adjacent, origin, normal, params, section_pts
            )
            return new_sel, new_adj, adj_rel, other_indices, warnings

        worker = _Worker(do_auto_join)
        self._worker = worker

        def on_done(result, err):
            if err:
                QMessageBox.critical(self, "Erro", f"Erro no encaixe automático:\n{err}")
                self._set_ready("Erro no encaixe.")
                return

            new_sel, new_adj, adj_rel, o_indices, warnings = result
            adj_abs_idx = o_indices[adj_rel]
            adj_name = self._part_names[adj_abs_idx]

            self._save_state()
            self._parts[idx] = new_sel
            self._parts[adj_abs_idx] = new_adj
            self._refresh_viewer()

            msg = f"Encaixe: pino em '{selected_name}', furo em '{adj_name}'"
            if warnings:
                QMessageBox.warning(self, "Avisos nos encaixes",
                    "Encaixes gerados com avisos:\n• " + "\n• ".join(warnings))
                self._set_ready(msg + f" ({len(warnings)} aviso(s))")
            else:
                self._set_ready(msg + "  ✓")

        worker.done.connect(on_done)
        worker.start()

    # ── Ações de corte manual ─────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir modelo 3D", "",
            "Modelos 3D (*.stl *.obj *.STL *.OBJ)"
        )
        if not path:
            return

        self._set_busy("Carregando modelo...")

        load_worker = _Worker(load_mesh, path)
        self._worker = load_worker

        def on_loaded(result, err):
            if err:
                self._set_ready("Erro ao carregar arquivo.")
                QMessageBox.critical(self, "Erro", err)
                return

            components, info = result

            if info["is_heavy"]:
                n = info["faces"]
                reply = QMessageBox.question(
                    self, "Modelo pesado detectado",
                    f"Este modelo tem {n:,} faces ({n/1_000_000:.1f}M).\n\n"
                    "Operações de encaixe (booleanas) podem ser muito lentas.\n\n"
                    f"Deseja simplificar para ~{SIMPLIFY_TARGET:,} faces?\n"
                    "(O arquivo original não é modificado.)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    self._status.showMessage("⏳  Simplificando mesh (aguarde)...")
                    target_each = max(10_000, SIMPLIFY_TARGET // max(1, len(components)))

                    def do_simplify():
                        return [simplify_mesh(c, target_each) for c in components]

                    simp_worker = _Worker(do_simplify)
                    self._worker = simp_worker

                    def on_simplified(simp_result, simp_err):
                        if not simp_err and simp_result:
                            total = sum(len(c.faces) for c in simp_result)
                            self._status.showMessage(f"Simplificado: {total:,} faces.")
                            self._finish_open(simp_result, info)
                        else:
                            self._finish_open(components, info)

                    simp_worker.done.connect(on_simplified)
                    simp_worker.start()
                    return

            self._finish_open(components, info)

        load_worker.done.connect(on_loaded)
        load_worker.start()

    def _finish_open(self, components: list, info: dict):
        base = info["name"].rsplit(".", 1)[0]
        if len(components) == 1:
            names = [base]
        else:
            pad = len(str(len(components)))
            names = [f"{base}_parte_{str(i+1).zfill(pad)}" for i in range(len(components))]

        self._original_parts = [p.copy() for p in components]
        self._original_names = names[:]
        self._parts = components
        self._part_names = names
        self._joint_info = {}
        self._history = []
        self._selected_idx = 0
        self._exploded = False
        self._btn_explode.setChecked(False)

        d = info["dims_mm"]
        self._lbl_name.setText(info["name"])
        self._lbl_verts.setText(f"Vértices: {info['vertices']:,}")
        self._lbl_faces.setText(f"Faces: {info['faces']:,}")
        self._lbl_dims.setText(f"Dims: {d[0]:.1f} × {d[1]:.1f} × {d[2]:.1f} mm")
        self._lbl_unit.setText(f"Unidade: {info['unit_hint']}")
        self._lbl_wt.setText(f"Watertight: {'Sim' if info['is_watertight'] else 'Não'}")
        nc = info["n_components"]
        self._lbl_comp.setText(
            f"Componentes: {nc}" + (" — separados automaticamente" if nc > 1 else "")
        )

        self.viewer.clear_all()
        self._refresh_parts_list()
        self._refresh_viewer()
        self.viewer.fit_view()

        msg = f"{info['name']}  |  {info['faces']:,} faces"
        if nc > 1:
            msg += f"  |  {nc} partes detectadas — use 'Pintar Parte' para selecionar"
        else:
            msg += "  |  Use 'Pintar Parte' para separar uma região"
        self._set_ready(msg)

    def _apply_cut(self):
        if not self._parts:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        ax = self._current_axis()
        pos = self._current_position()
        mesh = self._parts[idx]
        base_name = self._part_names[idx]

        self._set_busy(f"Cortando '{base_name}' em {ax.upper()} = {pos:.2f} mm...")

        worker = _Worker(cut_mesh, mesh, ax, pos)
        self._worker = worker

        def on_done(result, err):
            if err:
                QMessageBox.critical(self, "Erro no corte", err)
                self._set_ready("Erro no corte.")
                return

            part_a, part_b = result
            name_a = f"{base_name}_A"
            name_b = f"{base_name}_B"

            self._save_state()
            self._parts.pop(idx)
            self._part_names.pop(idx)
            self._parts.insert(idx, part_a)
            self._part_names.insert(idx, name_a)
            self._parts.insert(idx + 1, part_b)
            self._part_names.insert(idx + 1, name_b)
            self._joint_info[(name_a, name_b)] = (ax, pos)

            self._selected_idx = idx
            self._refresh_parts_list()
            self._refresh_viewer()
            self._set_ready(
                f"Corte: '{name_a}' e '{name_b}'  |  Total: {len(self._parts)} partes"
            )

        worker.done.connect(on_done)
        worker.start()

    def _apply_component_split(self):
        if not self._parts:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        mesh = self._parts[idx]
        base_name = self._part_names[idx]

        self._set_busy(f"Analisando componentes de '{base_name}'...")

        worker = _Worker(split_by_components, mesh)
        self._worker = worker

        def on_done(result, err):
            if err:
                QMessageBox.critical(self, "Erro", err)
                self._set_ready("Erro ao separar componentes.")
                return

            components = result
            if len(components) <= 1:
                self._set_ready(f"'{base_name}' já é um único componente.")
                QMessageBox.information(self, "Componentes",
                    f"'{base_name}' não possui corpos separados.\n"
                    "Use 'Pintar Parte' para separar por região,\n"
                    "ou o slider de corte manual.")
                return

            pad = len(str(len(components)))
            new_names = [
                f"{base_name}_parte_{str(i+1).zfill(pad)}"
                for i in range(len(components))
            ]

            self._save_state()
            self._parts.pop(idx)
            self._part_names.pop(idx)
            for i, (comp, name) in enumerate(zip(components, new_names)):
                self._parts.insert(idx + i, comp)
                self._part_names.insert(idx + i, name)

            self._selected_idx = idx
            self._refresh_parts_list()
            self._refresh_viewer()
            self._set_ready(
                f"'{base_name}' → {len(components)} componentes  |  Total: {len(self._parts)}"
            )

        worker.done.connect(on_done)
        worker.start()

    def _apply_joints(self):
        """Encaixe manual entre a parte selecionada e a próxima na lista."""
        if len(self._parts) < 2:
            QMessageBox.warning(self, "Aviso", "Faça pelo menos um corte antes de adicionar encaixes.")
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        if idx >= len(self._parts) - 1:
            QMessageBox.warning(self, "Aviso",
                "Selecione uma parte que tenha outra logo abaixo na lista.")
            return

        name_a = self._part_names[idx]
        name_b = self._part_names[idx + 1]
        part_a = self._parts[idx]
        part_b = self._parts[idx + 1]

        params = self._joint_params()

        cut_data = self._joint_info.get((name_a, name_b))
        if cut_data:
            ax, pos = cut_data
        else:
            ax = self._current_axis()
            pos = self._current_position()

        normal = AXIS_NORMALS[ax].copy()
        section_pts = get_cross_section_points(part_a, ax, pos)
        origin = section_pts.mean(axis=0)

        self._set_busy(f"Adicionando encaixe entre '{name_a}' e '{name_b}'...")

        def do_joints():
            return add_joints(part_a, part_b, origin, normal, params, section_pts)

        worker = _Worker(do_joints)
        self._worker = worker

        def on_done(result, err):
            if err:
                QMessageBox.critical(self, "Erro", f"Erro ao adicionar encaixes:\n{err}")
                self._set_ready("Erro nos encaixes.")
                return

            new_a, new_b, warnings = result
            self._save_state()
            self._parts[idx] = new_a
            self._parts[idx + 1] = new_b
            self._refresh_viewer()

            if warnings:
                QMessageBox.warning(self, "Avisos nos encaixes",
                    "Encaixes adicionados com avisos:\n• " + "\n• ".join(warnings))
                self._set_ready(f"Encaixes adicionados com {len(warnings)} aviso(s).")
            else:
                self._set_ready(f"Encaixe: pino em '{name_a}', furo em '{name_b}'  ✓")

        worker.done.connect(on_done)
        worker.start()

    def _rename_part(self, item: QListWidgetItem):
        idx = self._parts_list.row(item)
        old_name = self._part_names[idx]
        new_name, ok = QInputDialog.getText(
            self, "Renomear Parte", "Novo nome:", text=old_name)
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        new_name = new_name.strip()
        updated = {}
        for (a, b), data in self._joint_info.items():
            a2 = new_name if a == old_name else a
            b2 = new_name if b == old_name else b
            updated[(a2, b2)] = data
        self._joint_info = updated
        self._part_names[idx] = new_name
        self._refresh_parts_list()
        self._set_ready(f"Renomeado: '{old_name}' → '{new_name}'")

    def _undo(self):
        if not self._history:
            self._status.showMessage("Nada para desfazer.")
            return
        parts, names, joint_info, sel_idx = self._history.pop()
        self._parts = parts
        self._part_names = names
        self._joint_info = joint_info
        self._selected_idx = max(0, min(sel_idx, len(parts) - 1))
        self._refresh_parts_list()
        self._refresh_viewer()
        self._set_ready(f"Operação desfeita  |  {len(self._history)} restante(s)")

    def _reset(self):
        if not self._original_parts:
            return
        self._save_state()
        self._parts = [p.copy() for p in self._original_parts]
        self._part_names = self._original_names[:]
        self._joint_info = {}
        self._selected_idx = 0
        self._exploded = False
        self._btn_explode.setChecked(False)
        self._refresh_parts_list()
        self._refresh_viewer()
        self._set_ready("Resetado ao modelo original.")

    # ── Export ────────────────────────────────────────────────────────────────

    def _export(self):
        if not self._parts:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return
        if len(self._parts) == 1:
            r = QMessageBox.question(
                self, "Exportar",
                "Só há uma parte. Deseja exportar mesmo assim?",
                QMessageBox.Yes | QMessageBox.No
            )
            if r != QMessageBox.Yes:
                return

        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar ZIP", "partes_3d.zip", "ZIP (*.zip)"
        )
        if not path:
            return

        # Escolhe formato interno do ZIP
        fmt_items = ["STL  (.stl) — recomendado para impressão", "OBJ  (.obj)"]
        fmt, ok = QInputDialog.getItem(
            self, "Formato dos arquivos", "Formato:", fmt_items, 0, False
        )
        if not ok:
            return
        ext = ".stl" if "STL" in fmt else ".obj"

        self._set_busy("Exportando ZIP...")
        try:
            export_parts(self._parts, self._part_names, path, ext)
            self._set_ready(f"Exportado: {path}")
            QMessageBox.information(self, "Exportado!",
                f"{len(self._parts)} parte(s) salvas em:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro na exportação", str(e))
            self._set_ready("Erro na exportação.")

    def _export_single(self):
        if not self._parts:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        name = self._part_names[idx]
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar parte", f"{safe}.stl",
            "STL (*.stl);;OBJ (*.obj)"
        )
        if not path:
            return

        self._set_busy(f"Exportando '{name}'...")
        try:
            export_single_part(self._parts[idx], name, path)
            self._set_ready(f"'{name}' exportado: {path}")
            QMessageBox.information(self, "Exportado!", f"'{name}' salvo em:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            self._set_ready("Erro na exportação.")

    def _about(self):
        QMessageBox.information(self, "Sobre — ZefiroSplit",
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
            "  Use o slider e 'Aplicar Corte' para cortes precisos por plano.")
