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
from src import config as cfg
from src import logger as log_mod
from src.i18n import tr


_log = log_mod.get()


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
            _log.error("Worker falhou: %s", e, exc_info=True)
            self.done.emit(None, str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZefiroSplit")
        w = cfg.get("ui", "window_width", 1400)
        h = cfg.get("ui", "window_height", 900)
        self.resize(w, h)

        self._original_parts: list = []
        self._original_names: list = []
        self._parts: list = []
        self._part_names: list = []
        self._joint_info: dict = {}
        self._history: list = []
        self._selected_idx: int = 0
        self._pick_mode: bool = False
        self._wireframe: bool = False
        self._exploded: bool = False
        self._explode_factor: float = cfg.get("ui", "explode_factor", 2.5)
        self._history_max: int = cfg.get("ui", "history_max", 8)
        self._worker = None

        _log.info("ZefiroSplit iniciado. Idioma: %s", cfg.get_language())
        self._build_ui()

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        panel_w = cfg.get("ui", "panel_width", 340)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_panel())
        self.viewer = ViewerWidget(self)
        splitter.addWidget(self.viewer)
        splitter.setSizes([panel_w, 9999])
        self.setCentralWidget(splitter)

        bar = self.menuBar()
        fm = bar.addMenu(tr("menu_file"))
        fm.addAction(tr("menu_open"), self._open_file)
        fm.addSeparator()
        fm.addAction(tr("menu_export_zip"), self._export)
        fm.addAction(tr("menu_export_single"), self._export_single)
        fm.addSeparator()
        fm.addAction(tr("menu_quit"), self.close)

        vm = bar.addMenu(tr("menu_view"))
        vm.addAction(tr("menu_wireframe"), self._toggle_wireframe)
        vm.addAction(tr("menu_exploded"), self._toggle_exploded)
        vm.addAction(tr("menu_fit"), lambda: self.viewer.fit_view())

        lm = bar.addMenu(tr("menu_language"))
        lm.addAction(tr("menu_lang_pt"), lambda: self._set_language("pt"))
        lm.addAction(tr("menu_lang_en"), lambda: self._set_language("en"))

        hm = bar.addMenu(tr("menu_help"))
        hm.addAction(tr("menu_about"), self._about)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage(tr("status_ready"))

    def _build_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(cfg.get("ui", "panel_width", 340))
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(8, 8, 8, 8)

        btn_open = QPushButton(tr("btn_open"))
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
        btn_exp = QPushButton(tr("btn_export_zip"))
        btn_exp.setFixedHeight(38)
        btn_exp.setStyleSheet(
            "QPushButton{background:#2E7D32;color:white;font-weight:bold;font-size:12px;border-radius:5px;}"
            "QPushButton:hover{background:#388E3C;}")
        btn_exp.clicked.connect(self._export)
        btn_exp1 = QPushButton(tr("btn_export_part"))
        btn_exp1.setFixedHeight(38)
        btn_exp1.setToolTip(tr("tip_export_part"))
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
        grp = QGroupBox(tr("grp_info"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(3)
        self._lbl_name = QLabel("—")
        self._lbl_name.setStyleSheet("font-weight:bold;")
        self._lbl_verts = QLabel("—")
        self._lbl_faces = QLabel("—")
        self._lbl_dims = QLabel("—")
        self._lbl_unit = QLabel("—")
        self._lbl_wt = QLabel("—")
        self._lbl_comp = QLabel("—")
        self._lbl_comp.setStyleSheet("color:#4FC3F7;font-weight:bold;")
        for lbl in [self._lbl_name, self._lbl_verts, self._lbl_faces,
                    self._lbl_dims, self._lbl_unit, self._lbl_wt, self._lbl_comp]:
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        return grp

    def _build_paint_group(self) -> QGroupBox:
        grp = QGroupBox(tr("grp_paint"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(4)

        info = QLabel(tr("paint_hint"))
        info.setStyleSheet("color:#90CAF9;font-size:10px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        self._btn_pick = QPushButton(tr("btn_paint"))
        self._btn_pick.setCheckable(True)
        self._btn_pick.setFixedHeight(34)
        self._btn_pick.setStyleSheet(
            "QPushButton{background:#4527A0;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:checked{background:#7C4DFF;}"
            "QPushButton:hover{background:#512DA8;}")
        self._btn_pick.toggled.connect(self._toggle_pick_mode)
        lay.addWidget(self._btn_pick)

        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel(tr("lbl_angle")))
        self._spin_grow_angle = QDoubleSpinBox()
        self._spin_grow_angle.setRange(5.0, 90.0)
        self._spin_grow_angle.setValue(cfg.get("ui", "default_angle_deg", 30.0))
        self._spin_grow_angle.setDecimals(0)
        self._spin_grow_angle.setSuffix("°")
        self._spin_grow_angle.setToolTip(tr("tip_angle"))
        angle_row.addWidget(self._spin_grow_angle)
        lay.addLayout(angle_row)

        self._btn_auto_join = QPushButton(tr("btn_auto_join"))
        self._btn_auto_join.setFixedHeight(34)
        self._btn_auto_join.setStyleSheet(
            "QPushButton{background:#6A1B9A;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#7B1FA2;}")
        self._btn_auto_join.setToolTip(tr("tip_auto_join"))
        self._btn_auto_join.clicked.connect(self._auto_join_with_adjacent_selected)
        lay.addWidget(self._btn_auto_join)

        return grp

    def _build_cut_group(self) -> QGroupBox:
        grp = QGroupBox(tr("grp_cut"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(4)

        ax_row = QHBoxLayout()
        ax_row.addWidget(QLabel(tr("lbl_axis")))
        self._axis_grp = QButtonGroup(self)
        for label in ("X", "Y", "Z"):
            rb = QRadioButton(label)
            if label == "Z":
                rb.setChecked(True)
            self._axis_grp.addButton(rb)
            ax_row.addWidget(rb)
            rb.toggled.connect(self._on_axis_changed)
        lay.addLayout(ax_row)

        lay.addWidget(QLabel(tr("lbl_position")))
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(1000)
        self._slider.setValue(500)
        self._slider.valueChanged.connect(self._on_slider_changed)
        lay.addWidget(self._slider)
        self._lbl_pos = QLabel(tr("lbl_position_empty"))
        lay.addWidget(self._lbl_pos)

        self._btn_wire = QPushButton(tr("btn_wireframe"))
        self._btn_wire.setCheckable(True)
        self._btn_wire.setStyleSheet(
            "QPushButton{background:#37474F;color:white;border-radius:4px;}"
            "QPushButton:checked{background:#546E7A;}"
            "QPushButton:hover{background:#455A64;}")
        self._btn_wire.toggled.connect(self._set_wireframe)
        lay.addWidget(self._btn_wire)

        row_cut = QHBoxLayout()
        btn_cut = QPushButton(tr("btn_cut"))
        btn_cut.setStyleSheet(
            "QPushButton{background:#0277BD;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#0288D1;}")
        btn_cut.clicked.connect(self._apply_cut)
        btn_split = QPushButton(tr("btn_split_comp"))
        btn_split.setToolTip(tr("tip_split_comp"))
        btn_split.setStyleSheet(
            "QPushButton{background:#00695C;color:white;border-radius:4px;}"
            "QPushButton:hover{background:#00796B;}")
        btn_split.clicked.connect(self._apply_component_split)
        row_cut.addWidget(btn_cut)
        row_cut.addWidget(btn_split)
        lay.addLayout(row_cut)

        return grp

    def _build_joint_group(self) -> QGroupBox:
        grp = QGroupBox(tr("grp_joint"))
        lay = QVBoxLayout(grp)
        lay.setSpacing(4)

        def spin_row(label_key, val, mn, mx, dec, suffix):
            row = QHBoxLayout()
            row.addWidget(QLabel(tr(label_key)))
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

        self._spin_diam = spin_row("lbl_diam", cfg.get("joint", "pin_diameter_mm", 3.0), 1.0, 20.0, 1, " mm")
        self._spin_depth = spin_row("lbl_depth", cfg.get("joint", "pin_depth_mm", 8.0), 2.0, 50.0, 1, " mm")
        self._spin_tol = spin_row("lbl_tol", cfg.get("joint", "tolerance_mm", 0.2), 0.0, 2.0, 2, " mm")
        self._spin_pins = spin_row("lbl_pins", cfg.get("joint", "n_pins", 1), 1, 6, 0, "")

        btn_joint = QPushButton(tr("btn_add_joint"))
        btn_joint.setStyleSheet(
            "QPushButton{background:#4A148C;color:white;font-weight:bold;border-radius:4px;}"
            "QPushButton:hover{background:#6A1B9A;}")
        btn_joint.clicked.connect(self._apply_joints)
        lay.addWidget(btn_joint)

        return grp

    def _build_parts_group(self) -> QGroupBox:
        grp = QGroupBox(tr("grp_parts"))
        lay = QVBoxLayout(grp)

        self._parts_list = QListWidget()
        self._parts_list.setMaximumHeight(150)
        self._parts_list.currentRowChanged.connect(self._on_part_selected)
        self._parts_list.itemDoubleClicked.connect(self._rename_part)
        lay.addWidget(self._parts_list)

        row1 = QHBoxLayout()
        btn_undo = QPushButton(tr("btn_undo"))
        btn_undo.clicked.connect(self._undo)
        btn_reset = QPushButton(tr("btn_reset"))
        btn_reset.clicked.connect(self._reset)
        btn_fit = QPushButton(tr("btn_fit"))
        btn_fit.clicked.connect(lambda: self.viewer.fit_view())
        row1.addWidget(btn_undo)
        row1.addWidget(btn_reset)
        row1.addWidget(btn_fit)
        lay.addLayout(row1)

        self._btn_explode = QPushButton(tr("btn_explode"))
        self._btn_explode.setCheckable(True)
        self._btn_explode.setToolTip(tr("tip_explode"))
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
        self._lbl_pos.setText(tr("lbl_position_val", v=pos))
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
        if len(self._history) > self._history_max:
            self._history.pop(0)

    def _joint_params(self) -> JointParams:
        return JointParams(
            pin_diameter=self._spin_diam.value(),
            pin_depth=self._spin_depth.value(),
            tolerance=self._spin_tol.value(),
            n_pins=self._spin_pins.value(),
        )

    def _set_language(self, lang: str):
        cfg.set_language(lang)
        _log.info("Idioma alterado para: %s", lang)
        self._set_ready(tr("status_lang_restart"))

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
            angle = float(self._spin_grow_angle.value())
            if n == 1:
                self._status.showMessage(tr("status_paint_one", angle=angle))
            else:
                self._status.showMessage(tr("status_paint_many", n=n))
        else:
            self.viewer.deactivate_picking()
            self._status.showMessage(tr("status_paint_off"))

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
                self._status.showMessage(tr("status_exploded", n=len(self._parts)))
            else:
                self._status.showMessage(tr("status_normal_view"))

    # ── Pintura / seleção de componente ──────────────────────────────────────

    def _on_mesh_picked(self, point: np.ndarray):
        if not self._parts:
            return

        if len(self._parts) == 1:
            self._btn_pick.setChecked(False)
            mesh = self._parts[0]
            base_name = self._part_names[0]
            angle = float(self._spin_grow_angle.value())

            _log.info("Region growing em '%s', ângulo=%.0f°, ponto=%s", base_name, angle, point)
            self._set_busy(tr("status_ai_detecting", angle=angle))

            worker = _Worker(region_grow_and_cut, mesh, point, angle)
            self._worker = worker

            def on_grown(result, err):
                if err:
                    _log.error("Region growing falhou: %s", err)
                    self._set_ready(tr("status_error_cut"))
                    QMessageBox.warning(
                        self, tr("dlg_err_paint"),
                        tr("dlg_err_paint_msg", err=err),
                    )
                    return

                part_painted, part_base, cut_origin, cut_normal = result
                total = len(part_painted.faces) + len(part_base.faces)
                pct = len(part_painted.faces) / total * 100
                wt_p = tr("dlg_wt_closed") if part_painted.is_watertight else tr("dlg_wt_open")
                wt_b = tr("dlg_wt_closed") if part_base.is_watertight else tr("dlg_wt_open")

                _log.info(
                    "Região detectada: %d faces (%.0f%%), base: %d faces (%.0f%%)",
                    len(part_painted.faces), pct, len(part_base.faces), 100 - pct,
                )

                reply = QMessageBox.question(
                    self, tr("dlg_region_title"),
                    tr("dlg_region_msg",
                       pf=len(part_painted.faces), pp=pct, wtp=wt_p,
                       bf=len(part_base.faces), bp=100 - pct, wtb=wt_b),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )

                if reply == QMessageBox.No:
                    self._set_ready(tr("status_paint_cancel"))
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
                self._set_ready(tr("status_divided", a=name_painted, b=name_rest))

                self._auto_join_with_plane(0, cut_origin, cut_normal)

            worker.done.connect(on_grown)
            worker.start()

        else:
            from scipy.spatial import cKDTree
            min_dist = float("inf")
            best_idx = 0
            for i, mesh in enumerate(self._parts):
                verts = np.asarray(mesh.vertices, dtype=float)
                step = max(1, len(verts) // cfg.get("mesh", "kdtree_sample_size_a", 3000))
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
            _log.debug("Componente selecionado por proximidade: '%s'", name)
            self._status.showMessage(tr("status_selected", name=name))

    # ── Encaixe automático ────────────────────────────────────────────────────

    def _auto_join_with_plane(self, idx: int, cut_origin, cut_normal):
        """Usado após region_grow para inserir encaixe no plano detectado pela IA."""
        if len(self._parts) < 2:
            return
        other_idx = 1 if idx == 0 else 0
        part_a = self._parts[idx]
        part_b = self._parts[other_idx]
        name_a = self._part_names[idx]
        name_b = self._part_names[other_idx]
        params = self._joint_params()
        section_pts = np.array([cut_origin])

        _log.info("Encaixe automático (plano IA): '%s' ↔ '%s'", name_a, name_b)

        def do_joints():
            return add_joints(part_a, part_b, cut_origin, cut_normal, params, section_pts)

        worker = _Worker(do_joints)
        self._worker = worker

        def on_done(result, err):
            if err:
                _log.error("Encaixe auto (plano IA) falhou: %s", err)
                QMessageBox.critical(self, tr("dlg_warn_title"), tr("dlg_err_auto_joint", err=err))
                self._set_ready(tr("status_error_joint"))
                return

            new_a, new_b, warnings = result
            self._save_state()
            self._parts[idx] = new_a
            self._parts[other_idx] = new_b
            self._refresh_viewer()

            msg = tr("status_joint_done", a=name_a, b=name_b)
            if warnings:
                _log.warning("Encaixes com avisos: %s", warnings)
                QMessageBox.warning(
                    self, tr("dlg_warn_joint"),
                    tr("dlg_warn_joint_msg", warns="\n• ".join(warnings)),
                )
                self._set_ready(tr("status_joint_warns", a=name_a, b=name_b, n=len(warnings)))
            else:
                self._set_ready(msg + "  ✓")

        worker.done.connect(on_done)
        worker.start()

    def _auto_join_with_adjacent_selected(self):
        if not self._parts:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_no_parts"))
            return
        if len(self._parts) < 2:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_one_part_warn"))
            return
        self._auto_join_with_adjacent(min(self._selected_idx, len(self._parts) - 1))

    def _auto_join_with_adjacent(self, idx: int):
        selected = self._parts[idx]
        selected_name = self._part_names[idx]

        other_indices = [i for i in range(len(self._parts)) if i != idx]
        other_parts = [self._parts[i] for i in other_indices]

        params = self._joint_params()

        _log.info("Encaixe automático por adjacência para '%s'", selected_name)
        self._set_busy(tr("status_joint_detect", name=selected_name))

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
                _log.error("Encaixe auto por adjacência falhou: %s", err)
                QMessageBox.critical(self, tr("dlg_warn_title"), tr("dlg_err_auto_joint", err=err))
                self._set_ready(tr("status_error_joint"))
                return

            new_sel, new_adj, adj_rel, o_indices, warnings = result
            adj_abs_idx = o_indices[adj_rel]
            adj_name = self._part_names[adj_abs_idx]

            self._save_state()
            self._parts[idx] = new_sel
            self._parts[adj_abs_idx] = new_adj
            self._refresh_viewer()

            msg = tr("status_joint_done", a=selected_name, b=adj_name)
            if warnings:
                _log.warning("Encaixes com avisos: %s", warnings)
                QMessageBox.warning(
                    self, tr("dlg_warn_joint"),
                    tr("dlg_warn_joint_msg", warns="\n• ".join(warnings)),
                )
                self._set_ready(tr("status_joint_warns", a=selected_name, b=adj_name, n=len(warnings)))
            else:
                self._set_ready(msg + "  ✓")

        worker.done.connect(on_done)
        worker.start()

    # ── Ações de corte manual ─────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dlg_open_title"), "",
            tr("dlg_open_filter"),
        )
        if not path:
            return

        _log.info("Abrindo arquivo: %s", path)
        self._set_busy(tr("status_loading"))

        load_worker = _Worker(load_mesh, path)
        self._worker = load_worker

        def on_loaded(result, err):
            if err:
                _log.error("Erro ao carregar '%s': %s", path, err)
                self._set_ready(tr("status_error_load"))
                QMessageBox.critical(self, "Erro", err)
                return

            components, info = result

            if info["is_heavy"]:
                n = info["faces"]
                reply = QMessageBox.question(
                    self, tr("dlg_heavy_title"),
                    tr("dlg_heavy_msg", n=n, m=n / 1_000_000, t=SIMPLIFY_TARGET),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    _log.info("Simplificando mesh: %d → ~%d faces", n, SIMPLIFY_TARGET)
                    self._status.showMessage(f"⏳  {tr('status_simplifying')}")
                    target_each = max(10_000, SIMPLIFY_TARGET // max(1, len(components)))

                    def do_simplify():
                        return [simplify_mesh(c, target_each) for c in components]

                    simp_worker = _Worker(do_simplify)
                    self._worker = simp_worker

                    def on_simplified(simp_result, simp_err):
                        if not simp_err and simp_result:
                            total = sum(len(c.faces) for c in simp_result)
                            _log.info("Simplificação concluída: %d faces", total)
                            self._status.showMessage(tr("status_simplified", n=total))
                            self._finish_open(simp_result, info)
                        else:
                            _log.warning("Simplificação falhou, usando original.")
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
        self._lbl_verts.setText(tr("lbl_verts_val", n=info["vertices"]))
        self._lbl_faces.setText(tr("lbl_faces_val", n=info["faces"]))
        self._lbl_dims.setText(tr("lbl_dims_val", x=d[0], y=d[1], z=d[2]))
        self._lbl_unit.setText(tr("lbl_unit_val", v=info["unit_hint"]))
        self._lbl_wt.setText(tr("lbl_wt_yes") if info["is_watertight"] else tr("lbl_wt_no"))
        nc = info["n_components"]
        if nc > 1:
            self._lbl_comp.setText(tr("lbl_comp_auto", n=nc))
        else:
            self._lbl_comp.setText(tr("lbl_comp_val", n=nc))

        self.viewer.clear_all()
        self._refresh_parts_list()
        self._refresh_viewer()
        self.viewer.fit_view()

        if nc > 1:
            msg = tr("load_status_multi", name=info["name"], faces=info["faces"], n=nc)
        else:
            msg = tr("load_status_single", name=info["name"], faces=info["faces"])
        self._set_ready(msg)

    def _apply_cut(self):
        if not self._parts:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_no_parts"))
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        ax = self._current_axis()
        pos = self._current_position()
        mesh = self._parts[idx]
        base_name = self._part_names[idx]

        _log.info("Cortando '%s' em %s = %.2f mm", base_name, ax.upper(), pos)
        self._set_busy(tr("status_cutting", name=base_name, ax=ax.upper(), pos=pos))

        worker = _Worker(cut_mesh, mesh, ax, pos)
        self._worker = worker

        def on_done(result, err):
            if err:
                _log.error("Corte falhou: %s", err)
                QMessageBox.critical(self, tr("dlg_err_cut"), err)
                self._set_ready(tr("status_error_cut"))
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
            self._set_ready(tr("status_cut_done", a=name_a, b=name_b, n=len(self._parts)))

        worker.done.connect(on_done)
        worker.start()

    def _apply_component_split(self):
        if not self._parts:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_no_parts"))
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        mesh = self._parts[idx]
        base_name = self._part_names[idx]

        _log.info("Separando componentes de '%s'", base_name)
        self._set_busy(tr("status_analyzing", name=base_name))

        worker = _Worker(split_by_components, mesh)
        self._worker = worker

        def on_done(result, err):
            if err:
                _log.error("Separação de componentes falhou: %s", err)
                QMessageBox.critical(self, "Erro", err)
                self._set_ready(tr("status_error_comp"))
                return

            components = result
            if len(components) <= 1:
                _log.info("'%s' é um único componente.", base_name)
                self._set_ready(tr("status_single_comp", name=base_name))
                QMessageBox.information(
                    self, tr("dlg_comp_title"),
                    tr("dlg_single_comp", name=base_name),
                )
                return

            pad = len(str(len(components)))
            new_names = [
                f"{base_name}_parte_{str(i+1).zfill(pad)}"
                for i in range(len(components))
            ]

            _log.info("'%s' separado em %d componentes.", base_name, len(components))
            self._save_state()
            self._parts.pop(idx)
            self._part_names.pop(idx)
            for i, (comp, name) in enumerate(zip(components, new_names)):
                self._parts.insert(idx + i, comp)
                self._part_names.insert(idx + i, name)

            self._selected_idx = idx
            self._refresh_parts_list()
            self._refresh_viewer()
            self._set_ready(tr("status_comp_done", name=base_name, n=len(components), total=len(self._parts)))

        worker.done.connect(on_done)
        worker.start()

    def _apply_joints(self):
        if len(self._parts) < 2:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_need_cut"))
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        if idx >= len(self._parts) - 1:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_need_next"))
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

        _log.info("Encaixe manual: '%s' ↔ '%s', eixo=%s, pos=%.2f", name_a, name_b, ax, pos)
        self._set_busy(tr("status_joint_detect", name=name_a))

        def do_joints():
            return add_joints(part_a, part_b, origin, normal, params, section_pts)

        worker = _Worker(do_joints)
        self._worker = worker

        def on_done(result, err):
            if err:
                _log.error("Encaixe manual falhou: %s", err)
                QMessageBox.critical(self, "Erro", tr("dlg_err_joint", err=err))
                self._set_ready(tr("status_error_joint"))
                return

            new_a, new_b, warnings = result
            self._save_state()
            self._parts[idx] = new_a
            self._parts[idx + 1] = new_b
            self._refresh_viewer()

            if warnings:
                _log.warning("Encaixes manuais com avisos: %s", warnings)
                QMessageBox.warning(
                    self, tr("dlg_warn_joint"),
                    tr("dlg_warn_joint_msg2", warns="\n• ".join(warnings)),
                )
                self._set_ready(tr("status_joint_warns", a=name_a, b=name_b, n=len(warnings)))
            else:
                self._set_ready(tr("status_joint_done", a=name_a, b=name_b) + "  ✓")

        worker.done.connect(on_done)
        worker.start()

    def _rename_part(self, item: QListWidgetItem):
        idx = self._parts_list.row(item)
        old_name = self._part_names[idx]
        new_name, ok = QInputDialog.getText(
            self, tr("dlg_rename_title"), tr("dlg_rename_label"), text=old_name)
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
        _log.info("Parte renomeada: '%s' → '%s'", old_name, new_name)
        self._refresh_parts_list()
        self._set_ready(tr("status_renamed", old=old_name, new=new_name))

    def _undo(self):
        if not self._history:
            self._status.showMessage(tr("status_nothing_undo"))
            return
        parts, names, joint_info, sel_idx = self._history.pop()
        self._parts = parts
        self._part_names = names
        self._joint_info = joint_info
        self._selected_idx = max(0, min(sel_idx, len(parts) - 1))
        _log.info("Undo executado. Histórico restante: %d", len(self._history))
        self._refresh_parts_list()
        self._refresh_viewer()
        self._set_ready(tr("status_undo", n=len(self._history)))

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
        _log.info("Modelo resetado ao original.")
        self._refresh_parts_list()
        self._refresh_viewer()
        self._set_ready(tr("status_reset"))

    # ── Export ────────────────────────────────────────────────────────────────

    def _export(self):
        if not self._parts:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_no_parts"))
            return
        if len(self._parts) == 1:
            r = QMessageBox.question(
                self, tr("dlg_export_one_title"), tr("dlg_export_one_warn"),
                QMessageBox.Yes | QMessageBox.No,
            )
            if r != QMessageBox.Yes:
                return

        path, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_export_zip_title"), "partes_3d.zip", "ZIP (*.zip)"
        )
        if not path:
            return

        fmt_items = [tr("dlg_export_fmt_stl"), tr("dlg_export_fmt_obj")]
        fmt, ok = QInputDialog.getItem(
            self, tr("dlg_export_fmt_title"), tr("dlg_export_fmt_label"),
            fmt_items, 0, False,
        )
        if not ok:
            return
        ext = ".stl" if "STL" in fmt else ".obj"

        _log.info("Exportando ZIP: %s (%d partes, formato %s)", path, len(self._parts), ext)
        self._set_busy(tr("status_exporting_zip"))
        try:
            export_parts(self._parts, self._part_names, path, ext)
            _log.info("ZIP exportado com sucesso: %s", path)
            self._set_ready(tr("status_exported", path=path))
            QMessageBox.information(
                self, tr("dlg_export_ok_title"),
                tr("dlg_export_ok_zip", n=len(self._parts), path=path),
            )
        except Exception as e:
            _log.error("Exportação ZIP falhou: %s", e, exc_info=True)
            QMessageBox.critical(self, tr("dlg_err_export"), str(e))
            self._set_ready(tr("status_error_export"))

    def _export_single(self):
        if not self._parts:
            QMessageBox.warning(self, tr("dlg_warn_title"), tr("dlg_no_parts"))
            return

        idx = min(self._selected_idx, len(self._parts) - 1)
        name = self._part_names[idx]
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

        path, _ = QFileDialog.getSaveFileName(
            self, tr("dlg_export_part_title"), f"{safe}.stl",
            "STL (*.stl);;OBJ (*.obj)"
        )
        if not path:
            return

        _log.info("Exportando parte '%s': %s", name, path)
        self._set_busy(tr("status_exporting", name=name))
        try:
            export_single_part(self._parts[idx], name, path)
            _log.info("Parte exportada com sucesso: %s", path)
            self._set_ready(tr("status_exported_part", name=name, path=path))
            QMessageBox.information(
                self, tr("dlg_export_ok_title"),
                tr("dlg_export_ok_part", name=name, path=path),
            )
        except Exception as e:
            _log.error("Exportação de parte falhou: %s", e, exc_info=True)
            QMessageBox.critical(self, tr("dlg_err_export"), str(e))
            self._set_ready(tr("status_error_export"))

    def _about(self):
        from src import logger as lm
        log_info = tr("status_log_path", path=lm.log_path())
        QMessageBox.information(
            self, tr("about_title"),
            tr("about_text") + f"\n\n{log_info}",
        )
