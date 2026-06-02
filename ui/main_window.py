import os
import numpy as np

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QListWidget,
    QListWidgetItem, QButtonGroup, QRadioButton, QDoubleSpinBox,
    QSpinBox, QFileDialog, QMessageBox, QSplitter, QStatusBar,
    QSizePolicy, QToolButton,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QPalette

from ui.viewer_widget import ViewerWidget
from src.importer import load_mesh
from src.cutter import cut_mesh, get_cross_section_centroid, AXIS_NORMALS, AXIS_IDX
from src.joints import add_joints, JointParams
from src.exporter import export_parts


# ── Worker para operações pesadas (corte, encaixe) em thread separada ────────

class _Worker(QThread):
    done = pyqtSignal(object, str)  # (resultado, erro)

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


# ── Janela principal ─────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Part Splitter — MVP")
        self.resize(1300, 820)

        # Estado da aplicação
        self._mesh = None
        self._mesh_info = None
        self._parts: list = []
        self._part_names: list = []
        self._cut_records: list = []   # (idx_a, idx_b, axis, position)
        self._selected_idx: int = 0
        self._pick_mode: bool = False
        self._worker = None

        self._build_ui()

    # ── Construção da UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_panel())
        self.viewer = ViewerWidget(self)
        splitter.addWidget(self.viewer)
        splitter.setSizes([310, 990])
        self.setCentralWidget(splitter)

        bar = QMenuBar = self.menuBar()
        fm = bar.addMenu("Arquivo")
        fm.addAction("Abrir STL / OBJ...", self._open_file)
        fm.addSeparator()
        fm.addAction("Exportar ZIP...", self._export)
        fm.addSeparator()
        fm.addAction("Sair", self.close)
        hm = bar.addMenu("Ajuda")
        hm.addAction("Sobre", lambda: QMessageBox.information(
            self, "Sobre", "3D Part Splitter\nMVP — 2026\n\nImporte um STL, corte em partes,\nadicione encaixes e exporte o ZIP."))

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Pronto. Abra um arquivo STL ou OBJ para começar.")

    def _build_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(310)
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(8, 8, 8, 8)

        # Botão abrir
        btn_open = QPushButton("Abrir STL / OBJ")
        btn_open.setFixedHeight(40)
        btn_open.setStyleSheet(
            "QPushButton{background:#1565C0;color:white;font-weight:bold;font-size:13px;border-radius:5px;}"
            "QPushButton:hover{background:#1976D2;}")
        btn_open.clicked.connect(self._open_file)
        lay.addWidget(btn_open)

        lay.addWidget(self._build_info_group())
        lay.addWidget(self._build_cut_group())
        lay.addWidget(self._build_joint_group())
        lay.addWidget(self._build_parts_group())

        # Botão exportar
        btn_exp = QPushButton("Exportar ZIP")
        btn_exp.setFixedHeight(40)
        btn_exp.setStyleSheet(
            "QPushButton{background:#2E7D32;color:white;font-weight:bold;font-size:13px;border-radius:5px;}"
            "QPushButton:hover{background:#388E3C;}")
        btn_exp.clicked.connect(self._export)
        lay.addWidget(btn_exp)

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
        self._lbl_wt = QLabel("Watertight: —")
        for l in [self._lbl_name, self._lbl_verts, self._lbl_faces,
                  self._lbl_dims, self._lbl_wt]:
            l.setWordWrap(True)
            lay.addWidget(l)
        return grp

    def _build_cut_group(self) -> QGroupBox:
        grp = QGroupBox("Corte por plano")
        lay = QVBoxLayout(grp)
        lay.setSpacing(4)

        # Eixo
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

        # Slider de posição
        lay.addWidget(QLabel("Posição:"))
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.setValue(500)
        self._slider.valueChanged.connect(self._on_slider_changed)
        lay.addWidget(self._slider)
        self._lbl_pos = QLabel("Posição: —")
        lay.addWidget(self._lbl_pos)

        # Botão conta-gota
        self._btn_pick = QPushButton("Conta-gota (clique na mesh)")
        self._btn_pick.setCheckable(True)
        self._btn_pick.setStyleSheet(
            "QPushButton{background:#4527A0;color:white;border-radius:4px;}"
            "QPushButton:checked{background:#7C4DFF;}"
            "QPushButton:hover{background:#512DA8;}")
        self._btn_pick.toggled.connect(self._toggle_pick_mode)
        lay.addWidget(self._btn_pick)

        # Botão cortar
        btn_cut = QPushButton("Aplicar Corte")
        btn_cut.setStyleSheet(
            "QPushButton{background:#0277BD;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#0288D1;}")
        btn_cut.clicked.connect(self._apply_cut)
        lay.addWidget(btn_cut)

        return grp

    def _build_joint_group(self) -> QGroupBox:
        grp = QGroupBox("Encaixe automático (pino + furo)")
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
            "QPushButton{background:#6A1B9A;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#7B1FA2;}")
        btn_joint.clicked.connect(self._apply_joints)
        lay.addWidget(btn_joint)

        return grp

    def _build_parts_group(self) -> QGroupBox:
        grp = QGroupBox("Partes")
        lay = QVBoxLayout(grp)

        self._parts_list = QListWidget()
        self._parts_list.setMaximumHeight(150)
        self._parts_list.currentRowChanged.connect(self._on_part_selected)
        lay.addWidget(self._parts_list)

        row = QHBoxLayout()
        btn_reset = QPushButton("Resetar")
        btn_reset.clicked.connect(self._reset)
        btn_fitview = QPushButton("Encaixar câmera")
        btn_fitview.clicked.connect(lambda: self.viewer.fit_view())
        row.addWidget(btn_reset)
        row.addWidget(btn_fitview)
        lay.addLayout(row)

        return grp

    # ── Helpers de estado ────────────────────────────────────────────────────

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
        if not self._parts:
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
        self.viewer.show_parts(self._parts, self._part_names, self._selected_idx)
        self._refresh_cut_plane()

    def _set_busy(self, msg: str):
        self._status.showMessage(f"⏳  {msg}")
        self.setEnabled(False)

    def _set_ready(self, msg: str):
        self._status.showMessage(msg)
        self.setEnabled(True)

    # ── Eventos ──────────────────────────────────────────────────────────────

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
            self._status.showMessage("Modo conta-gota ativo — clique na mesh para posicionar o corte.")
        else:
            self.viewer.disable_picking()
            self._status.showMessage("Modo conta-gota desativado.")

    def _on_mesh_picked(self, point: np.ndarray):
        """Chamado quando o usuário clica na mesh no modo conta-gota."""
        if not self._parts:
            return
        ax = self._current_axis()
        ai = AXIS_IDX[ax]
        idx = min(self._selected_idx, len(self._parts) - 1)
        mesh = self._parts[idx]

        lo = mesh.bounds[0][ai]
        hi = mesh.bounds[1][ai]
        picked_val = float(np.clip(point[ai], lo, hi))

        # Converte para valor do slider (0-1000)
        span = hi - lo
        if span > 1e-6:
            t = (picked_val - lo) / span
            self._slider.setValue(int(t * 1000))

        self._status.showMessage(
            f"Conta-gota: posição capturada em {ax.upper()}={picked_val:.2f} mm")

    # ── Ações principais ─────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir modelo 3D", "",
            "Modelos 3D (*.stl *.obj *.STL *.OBJ)"
        )
        if not path:
            return

        self._set_busy("Carregando modelo...")
        try:
            mesh, info = load_mesh(path)
        except Exception as e:
            self._set_ready("Erro ao carregar arquivo.")
            QMessageBox.critical(self, "Erro", str(e))
            return

        self._mesh = mesh
        self._mesh_info = info
        self._parts = [mesh]
        self._part_names = [info["name"].rsplit(".", 1)[0]]
        self._cut_records = []
        self._selected_idx = 0

        d = info["dims_mm"]
        self._lbl_name.setText(info["name"])
        self._lbl_verts.setText(f"Vértices: {info['vertices']:,}")
        self._lbl_faces.setText(f"Faces: {info['faces']:,}")
        self._lbl_dims.setText(f"Dims: {d[0]:.1f} × {d[1]:.1f} × {d[2]:.1f} mm")
        self._lbl_wt.setText(f"Watertight: {'Sim' if info['is_watertight'] else 'Não'}")

        self.viewer.clear_all()
        self._refresh_parts_list()
        self._refresh_viewer()
        self.viewer.fit_view()
        self._set_ready(
            f"Modelo carregado: {info['name']}  |  {info['vertices']:,} vértices  |  {info['faces']:,} faces"
        )

    def _apply_cut(self):
        if not self._parts:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        ax = self._current_axis()
        pos = self._current_position()
        mesh = self._parts[idx]
        base_name = self._part_names[idx]

        self._set_busy(f"Cortando '{base_name}' no eixo {ax.upper()} em {pos:.2f} mm...")

        def do_cut():
            return cut_mesh(mesh, ax, pos)

        self._worker = _Worker(do_cut)

        def on_done(result, err):
            if err:
                QMessageBox.critical(self, "Erro no corte", err)
                self._set_ready("Erro no corte.")
                return

            part_a, part_b = result
            name_a = f"{base_name}_A"
            name_b = f"{base_name}_B"

            self._parts.pop(idx)
            self._part_names.pop(idx)
            self._parts.insert(idx, part_a)
            self._part_names.insert(idx, name_a)
            self._parts.insert(idx + 1, part_b)
            self._part_names.insert(idx + 1, name_b)
            self._cut_records.append((idx, idx + 1, ax, pos))
            self._selected_idx = idx

            self._refresh_parts_list()
            self._refresh_viewer()
            self._set_ready(
                f"Corte aplicado: '{name_a}' e '{name_b}'  |  Total: {len(self._parts)} partes"
            )

        self._worker.done.connect(on_done)
        self._worker.start()

    def _apply_joints(self):
        if len(self._parts) < 2:
            QMessageBox.warning(self, "Aviso", "Faça pelo menos um corte antes de adicionar encaixes.")
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        if idx >= len(self._parts) - 1:
            QMessageBox.warning(self, "Aviso",
                "Selecione uma parte que tenha outra parte logo abaixo na lista.")
            return

        params = JointParams(
            pin_diameter=self._spin_diam.value(),
            pin_depth=self._spin_depth.value(),
            tolerance=self._spin_tol.value(),
            n_pins=self._spin_pins.value(),
        )

        # Descobre eixo e posição do corte que gerou este par (se houver registro)
        ax = self._current_axis()
        record = next(
            (r for r in self._cut_records if r[0] == idx and r[1] == idx + 1),
            None
        )
        if record:
            ax, pos = record[2], record[3]
        else:
            pos = self._current_position()

        normal = AXIS_NORMALS[ax].copy()
        part_a = self._parts[idx]
        part_b = self._parts[idx + 1]

        # Pontos da seção para distribuir os pinos
        try:
            from src.cutter import AXIS_NORMALS as _AN
            import trimesh as _tm
            lines = _tm.intersections.mesh_plane(part_a, normal,
                np.array([0.0, 0.0, 0.0]) if pos == 0
                else normal * pos)
            if lines is not None and len(lines) > 0:
                section_pts = np.array(lines).reshape(-1, 3)
            else:
                section_pts = np.array([get_cross_section_centroid(part_a, ax, pos)])
        except Exception:
            section_pts = np.array([get_cross_section_centroid(part_a, ax, pos)])

        origin = get_cross_section_centroid(part_a, ax, pos)
        name_a = self._part_names[idx]
        name_b = self._part_names[idx + 1]

        self._set_busy(f"Adicionando encaixes entre '{name_a}' e '{name_b}' (pode demorar)...")

        def do_joints():
            return add_joints(part_a, part_b, origin, normal, params, section_pts)

        self._worker = _Worker(do_joints)

        def on_done(result, err):
            if err:
                QMessageBox.critical(self, "Erro", f"Erro ao adicionar encaixes:\n{err}")
                self._set_ready("Erro nos encaixes.")
                return

            new_a, new_b = result
            self._parts[idx] = new_a
            self._parts[idx + 1] = new_b
            self._refresh_viewer()
            self._set_ready(f"Encaixe adicionado: pino em '{name_a}', furo em '{name_b}'")

        self._worker.done.connect(on_done)
        self._worker.start()

    def _reset(self):
        if self._mesh is None:
            return
        base = self._part_names[0].split("_")[0] if self._part_names else "modelo"
        self._parts = [self._mesh]
        self._part_names = [base]
        self._cut_records = []
        self._selected_idx = 0
        self._refresh_parts_list()
        self._refresh_viewer()
        self._set_ready("Resetado ao modelo original.")

    def _export(self):
        if not self._parts:
            QMessageBox.warning(self, "Aviso", "Nenhum modelo carregado.")
            return
        if len(self._parts) == 1:
            r = QMessageBox.question(
                self, "Exportar",
                "Só há uma parte. Deseja exportar o modelo original?",
                QMessageBox.Yes | QMessageBox.No
            )
            if r != QMessageBox.Yes:
                return

        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar ZIP", "partes_3d.zip", "ZIP (*.zip)"
        )
        if not path:
            return

        self._set_busy("Exportando ZIP...")
        try:
            export_parts(self._parts, self._part_names, path)
            self._set_ready(f"Exportado: {path}")
            QMessageBox.information(self, "Exportado com sucesso!",
                f"{len(self._parts)} parte(s) salva(s) em:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro na exportação", str(e))
            self._set_ready("Erro na exportação.")
