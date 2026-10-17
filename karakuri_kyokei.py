# からくり極刑ショー  -  Pyxel prototype (stage 1)
# 操作: 左クリック=配置/撤去  右クリック=撤去  SPACE=開始  R=編集に戻る
import random
import pyxel

W, H = 240, 200
COLS, ROWS, CS = 14, 9, 16
OX, OY = 8, 22
STEP_FRAMES = 4
MAX_STEPS = 180
BALLS = 3          # 鉄球は悪人に当たると消費。計3発

EMPTY, BLOCK, SPRING, DOMINO, TARAI, ARM = range(6)
PARTS = [(BLOCK, "BLOCK", 6), (SPRING, "SPRING", 2), (DOMINO, "DOMINO", 4),
         (TARAI, "TARAI", 1), (ARM, "TICKLE", 1)]
START = (0, 0)
VILLAIN = (12, 8)
STAGE = {
    "name": "GONZO the Head-Slapper",
    "crime": "Slapped every bald head in town. 108 counts.",
    "karma": TARAI,          # 頭を叩いた男には、頭上からのタライ
    "hp": 70,
}
CRY = {"ball": ["GUEH!", "OOF!", "GAH!"], "head": ["MY HEAD!", "BONK!"],
       "domino": ["OUCH!", "EEK!"], "tarai": ["GWAAAN!!"], "tickle": ["HYAHYA!", "STOP IT!"]}


class Game:
    def __init__(self):
        pyxel.init(W, H, title="Karakuri Kyokei Show", fps=30)
        pyxel.mouse(True)
        self.setup_sound()
        self.best = 0
        self.clear_board()
        self.mode = "edit"
        pyxel.run(self.update, self.draw)

    # ---- SE: 1イベント1音、全部合成。データ無しで完結させる ----
    def setup_sound(self):
        s = pyxel.sounds
        s[0].set("c4", "p", "4", "f", 5)                              # 配置: 乾いたクリック
        s[1].set("g4c4", "n", "53", "f", 4)                           # 撤去
        s[2].set("c2a1", "n", "76", "nf", 7)                          # 鉄球ヒット: 鈍いボコッ
        s[3].set("a3a3a3a3a3a3", "s", "765432", "vvvvvf", 12)         # タライ: グワァン(余韻)
        s[4].set("c2g2c3g3c4", "t", "66666", "nnnnf", 3)              # バネ: ビヨン↑
        s[5].set("a4", "n", "3", "f", 3)                              # ドミノ: カチッ
        s[6].set("e3g3e3g3", "p", "3", "n", 3)                        # くすぐり: ピロピロ
        s[7].set("c3e3g3c4e4g4", "t", "555543", "nnnnnv", 10)         # 昇天: 間抜けな上昇音
        s[8].set("c3e3g3c4", "s", "5", "nnnf", 6)                     # 開始ファンファーレ
        s[9].set("g3e3c3", "t", "543", "nnf", 10)                     # 恩赦(失敗)

    def se(self, n, ch=3):
        pyxel.play(ch, n)

    # ---------------- edit ----------------
    def clear_board(self):
        self.grid = [[EMPTY] * COLS for _ in range(ROWS)]
        self.stock = {p: n for p, _, n in PARTS}
        self.sel = BLOCK

    def cell_at(self, mx, my):
        if OX <= mx < OX + COLS * CS and OY <= my < OY + ROWS * CS:
            return (mx - OX) // CS, (my - OY) // CS
        return None

    def update_edit(self):
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        lp = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        rp = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
        if lp and 174 <= my < 198 and mx < 164:
            i = (mx - 4) // 32
            if 0 <= i < len(PARTS):
                self.sel = PARTS[i][0]
                self.se(0)
            return
        if lp and 170 <= mx < 236 and 174 <= my < 186 or pyxel.btnp(pyxel.KEY_SPACE):
            self.start_run()
            return
        if lp and 170 <= mx < 236 and 188 <= my < 198:
            self.clear_board()
            self.se(1)
            return
        c = self.cell_at(mx, my)
        if not c or c in (START, VILLAIN):
            return
        x, y = c
        cur = self.grid[y][x]
        if (lp or rp) and cur != EMPTY:
            self.grid[y][x] = EMPTY
            self.stock[cur] += 1
            self.se(1)
        elif lp and self.stock[self.sel] > 0:
            self.grid[y][x] = self.sel
            self.stock[self.sel] -= 1
            self.se(0)

    # ---------------- run ----------------
    def start_run(self):
        self.cells, self.dom, self.arms, self.tarais = {}, {}, {}, []
        for y in range(ROWS):
            for x in range(COLS):
                p = self.grid[y][x]
                if p == TARAI:
                    self.tarais.append({"x": x, "y": y, "st": "hang"})
                elif p != EMPTY:
                    self.cells[(x, y)] = p
                    if p == DOMINO:
                        self.dom[(x, y)] = 0
                    if p == ARM:
                        self.arms[(x, y)] = 0
        self.ball = {"x": START[0], "y": START[1], "dx": 1, "jump": 0}
        self.balls_left, self.respawn, self.idle = BALLS - 1, 0, 0
        self.v = {"hp": STAGE["hp"], "agony": 0, "dead": False, "soul": 0}
        self.steps = self.frame = 0
        self.pending = []
        self.combo, self.last_hit, self.max_combo = 0, -99, 0
        self.hit_pts = self.agony_steps = 0
        self.dead_step = None
        self.fx, self.texts = [], []
        self.mode = "run"
        self.se(8)

    def is_villain(self, x, y):
        return (x, y) == VILLAIN

    def solid(self, x, y):
        if x < 0 or x >= COLS or y < 0 or y >= ROWS:
            return True
        p = self.cells.get((x, y))
        if p in (BLOCK, ARM):
            return True
        if p == DOMINO and self.dom[(x, y)] == 0:
            return True
        return any(t["st"] == "rest" and t["x"] == x and t["y"] == y for t in self.tarais)

    def tarai_at(self, x, y):
        for t in self.tarais:
            if t["st"] == "hang" and t["x"] == x and t["y"] == y:
                return t
        return None

    def touch(self, x, y, d, src):
        """(x,y) に横から何かが当たった"""
        if self.is_villain(x, y):
            self.hit(15 if src == "ball" else 10, src)
            return
        p = self.cells.get((x, y))
        if p == DOMINO and self.dom[(x, y)] == 0:
            self.dom[(x, y)] = d
            self.pending.append((x + d, y, d))
            self.se(5, 2)
        elif p == ARM:
            self.activate_arm(x, y)
        t = self.tarai_at(x, y)
        if t:
            self.drop_tarai(t)

    def activate_arm(self, x, y):
        if self.arms[(x, y)] == 0:
            self.arms[(x, y)] = 24
            self.se(6, 2)

    def drop_tarai(self, t):
        t["st"] = "fall"

    def enter(self, b):
        x, y = b["x"], b["y"]
        if self.cells.get((x, y)) == SPRING:
            b["jump"] = 3
            self.se(4, 1)
        t = self.tarai_at(x, y)
        if t:
            self.drop_tarai(t)

    def spend_ball(self):
        self.ball = None
        self.respawn = 10

    def step_ball(self):
        b = self.ball
        if b is None:
            if self.balls_left > 0:
                self.respawn -= 1
                if self.respawn <= 0:
                    self.balls_left -= 1
                    self.ball = {"x": START[0], "y": START[1], "dx": 1, "jump": 0}
                    self.se(0)
            return
        x, y = b["x"], b["y"]
        if b["jump"] > 0:
            b["jump"] -= 1
            nx, ny = x + b["dx"], y - 1
            if self.is_villain(nx, ny) or self.solid(nx, ny):
                if self.is_villain(nx, ny):
                    self.touch(nx, ny, b["dx"], "ball")
                    self.spend_ball()
                    return
                self.touch(nx, ny, b["dx"], "ball")
                b["jump"] = 0
                if self.solid(nx, ny) or self.is_villain(nx, ny):
                    b["dx"] *= -1
                return
            b["x"], b["y"] = nx, ny
            self.enter(b)
            return
        if self.is_villain(x, y + 1):              # 脳天直撃
            self.hit(15, "head")
            self.spend_ball()
            return
        if not self.solid(x, y + 1):              # 落下
            b["y"] += 1
            self.enter(b)
            if self.solid(b["x"], b["y"] + 1) and self.cells.get((b["x"], b["y"] + 1)) == ARM:
                self.activate_arm(b["x"], b["y"] + 1)
            return
        nx = x + b["dx"]                          # 転がる
        if self.is_villain(nx, y):
            self.touch(nx, y, b["dx"], "ball")
            self.spend_ball()
            return
        if self.solid(nx, y):
            self.touch(nx, y, b["dx"], "ball")
            if self.is_villain(nx, y) or self.solid(nx, y):
                b["dx"] *= -1
            return
        b["x"] = nx
        self.enter(b)

    def hit(self, dmg, src):
        v = self.v
        if v["dead"]:
            return
        if src == "tickle":
            pts = dmg * 10
        else:
            self.combo = self.combo + 1 if self.steps - self.last_hit <= 4 else 1
            self.last_hit = self.steps
            self.max_combo = max(self.max_combo, self.combo)
            pts = dmg * 10 * self.combo
        karma = src == "tarai" and STAGE["karma"] == TARAI
        if karma:
            pts *= 2
        self.hit_pts += pts
        v["hp"] -= dmg
        v["agony"] = 6
        vx, vy = self.vpos()
        if src != "tickle" or self.steps % 4 == 0:
            self.float_text(random.choice(CRY[src]), vx + 8, vy - 6, 8)
            self.float_text("+%d" % pts, vx + 8, vy - 14, 10)
        if self.combo >= 2 and src != "tickle":
            self.float_text("COMBO x%d" % self.combo, vx - 8, vy - 22, 9)
        if karma:
            self.float_text("KARMA x2!", vx - 4, vy - 30, 14)
        for _ in range(6 if src != "tickle" else 1):
            self.fx.append([vx + 8, vy + 4, random.uniform(-2, 2), random.uniform(-3, -1), 12])
        if src != "tickle":
            self.se(3 if src == "tarai" else 2, 0)
        if v["hp"] <= 0:
            v["hp"], v["dead"] = 0, True
            self.dead_step = self.steps
            self.se(7, 1)

    def float_text(self, s, x, y, col):
        self.texts.append([s, x - len(s) * 2, y, col, 24])

    def step(self):
        self.steps += 1
        todo, self.pending = self.pending, []
        for x, y, d in todo:
            self.touch(x, y, d, "domino")
        for t in self.tarais:
            if t["st"] != "fall":
                continue
            ny = t["y"] + 1
            if self.is_villain(t["x"], ny) and not self.v["dead"]:
                self.hit(30, "tarai")
                t["st"] = "gone"
            elif self.solid(t["x"], ny) or self.is_villain(t["x"], ny):
                t["st"] = "rest"
                self.se(3, 0)
            else:
                t["y"] = ny
        for (ax, ay), tm in self.arms.items():
            if tm > 0:
                self.arms[(ax, ay)] = tm - 1
                if abs(ax - VILLAIN[0]) + abs(ay - VILLAIN[1]) == 1 and tm % 2 == 0:
                    self.hit(2, "tickle")
                    if tm % 6 == 0:
                        self.se(6, 2)
        self.step_ball()
        v = self.v
        if not v["dead"] and v["agony"] > 0:
            self.agony_steps += 1
        v["agony"] = max(0, v["agony"] - 1)
        busy = (self.ball is not None or self.balls_left > 0 or self.pending
                or any(t["st"] == "fall" for t in self.tarais) or any(self.arms.values()) or v["agony"])
        self.idle = 0 if busy else self.idle + 1
        if self.idle >= 10 or (self.dead_step is not None and self.steps - self.dead_step >= 15) or self.steps >= MAX_STEPS:
            self.finish()

    def finish(self):
        self.agony_pts = self.agony_steps * 25
        total = self.hit_pts + self.agony_pts
        self.pardoned = not self.v["dead"]
        if self.pardoned:
            total = int(total * 0.3)
            self.se(9, 1)
        self.total = total
        self.new_best = total > self.best
        self.best = max(self.best, total)
        self.mode = "result"

    def update_run(self):
        if pyxel.btnp(pyxel.KEY_R):
            self.mode = "edit"
            return
        self.frame += 1
        if self.frame % STEP_FRAMES == 0:
            self.step()
        if self.v["dead"]:
            self.v["soul"] += 1
        for p in self.fx:
            p[0] += p[2]; p[1] += p[3]; p[3] += 0.3; p[4] -= 1
        self.fx = [p for p in self.fx if p[4] > 0]
        for t in self.texts:
            t[2] -= 0.5; t[4] -= 1
        self.texts = [t for t in self.texts if t[4] > 0]

    def update(self):
        if self.mode == "edit":
            self.update_edit()
        elif self.mode == "run":
            self.update_run()
        elif pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) or pyxel.btnp(pyxel.KEY_SPACE) or pyxel.btnp(pyxel.KEY_R):
            self.mode = "edit"

    # ---------------- draw ----------------
    def vpos(self):
        return OX + VILLAIN[0] * CS, OY + VILLAIN[1] * CS

    def draw_part(self, p, px, py, state=0, active=False):
        if p == BLOCK:
            pyxel.rect(px, py, CS, CS, 13)
            pyxel.rectb(px, py, CS, CS, 5)
            pyxel.line(px, py + 8, px + 15, py + 8, 5)
            pyxel.line(px + 8, py, px + 8, py + 8, 5)
        elif p == SPRING:
            for i in range(4):
                pyxel.line(px + 3, py + 15 - i * 3, px + 12, py + 13 - i * 3, 10)
            pyxel.rect(px + 2, py + 4, 12, 2, 9)
        elif p == DOMINO:
            if state == 0:
                pyxel.rect(px + 5, py + 1, 6, 15, 7)
                pyxel.pset(px + 7, py + 4, 0); pyxel.pset(px + 8, py + 11, 0)
            else:
                ox = px + (8 if state > 0 else -7)
                pyxel.rect(ox, py + 10, 15, 6, 7)
                pyxel.pset(ox + 4, py + 12, 0); pyxel.pset(ox + 11, py + 13, 0)
        elif p == TARAI:
            pyxel.line(px + 8, py, px + 8, py + 6, 4)
            pyxel.tri(px + 1, py + 7, px + 14, py + 7, px + 8, py + 14, 10)
            pyxel.rect(px + 4, py + 7, 8, 5, 10)
            pyxel.line(px + 1, py + 7, px + 14, py + 7, 9)
        elif p == ARM:
            pyxel.rect(px + 2, py + 10, 12, 6, 6)
            wig = (pyxel.frame_count // 2) % 3 - 1 if active else 0
            pyxel.line(px + 8, py + 10, px + 8 + wig, py + 4, 6)
            pyxel.line(px + 8 + wig, py + 4, px + 12 + wig, py + 1, 14)
            pyxel.line(px + 9 + wig, py + 4, px + 13 + wig, py + 3, 14)

    def draw_villain(self):
        x, y = self.vpos()
        v = self.v if self.mode != "edit" else {"agony": 0, "dead": False, "soul": 0}
        sx = random.randint(-1, 1) if v["agony"] and not v["dead"] else 0
        x += sx
        skin = 13 if v["dead"] else 15
        for i in range(4):                                   # 囚人服
            pyxel.rect(x + 4, y + 8 + i * 2, 8, 1, 7)
            pyxel.rect(x + 4, y + 9 + i * 2, 8, 1, 0)
        pyxel.circ(x + 8, y + 5, 4, skin)
        for i in range(3):                                   # トゲトゲ頭
            pyxel.pset(x + 6 + i * 2, y, 0)
        if v["dead"] or v["agony"]:
            for ex in (x + 6, x + 10):
                pyxel.pset(ex - 1, y + 3, 0); pyxel.pset(ex + 1, y + 5, 0)
                pyxel.pset(ex + 1, y + 3, 0); pyxel.pset(ex - 1, y + 5, 0)
            pyxel.circ(x + 8, y + 7, 1, 0)
            if not v["dead"]:
                pyxel.pset(x + 13, y + 2 + (pyxel.frame_count // 3) % 3, 12)
        else:
            pyxel.pset(x + 6, y + 4, 0); pyxel.pset(x + 10, y + 4, 0)
            pyxel.line(x + 6, y + 7, x + 10, y + 6, 0)       # にやけ顔
        if v["dead"]:
            sy = y - v["soul"] // 2
            sx2 = x + 8 + int(pyxel.sin(v["soul"] * 12) * 3)
            pyxel.circ(sx2, sy, 3, 7)
            pyxel.tri(sx2 - 3, sy, sx2 + 3, sy, sx2 + 4, sy + 6, 7)
            pyxel.pset(sx2 - 1, sy - 1, 0); pyxel.pset(sx2 + 1, sy - 1, 0)

    def draw(self):
        pyxel.cls(1)
        pyxel.text(4, 3, "WANTED: " + STAGE["name"], 8)
        pyxel.text(4, 11, STAGE["crime"], 6)
        pyxel.rect(OX, OY, COLS * CS, ROWS * CS, 0)
        for gy in range(ROWS):
            for gx in range(COLS):
                pyxel.pset(OX + gx * CS, OY + gy * CS, 5)
        pyxel.rect(OX, OY + ROWS * CS, COLS * CS, 4, 4)
        # chute
        pyxel.rect(OX, OY, 14, 4, 13)
        pyxel.text(OX + 2, OY + 6, ">", 10)

        if self.mode == "edit":
            for y in range(ROWS):
                for x in range(COLS):
                    if self.grid[y][x]:
                        self.draw_part(self.grid[y][x], OX + x * CS, OY + y * CS)
            pyxel.circ(OX + 8, OY + 9, 4, 13)
            c = self.cell_at(pyxel.mouse_x, pyxel.mouse_y)
            if c and c not in (START, VILLAIN):
                pyxel.rectb(OX + c[0] * CS, OY + c[1] * CS, CS, CS, 10)
        else:
            for (x, y), p in self.cells.items():
                self.draw_part(p, OX + x * CS, OY + y * CS, self.dom.get((x, y), 0),
                               self.arms.get((x, y), 0) > 0)
            for t in self.tarais:
                if t["st"] != "gone":
                    self.draw_part(TARAI, OX + t["x"] * CS, OY + t["y"] * CS)
            b = self.ball
            if b:
              bx, by = OX + b["x"] * CS + 8, OY + b["y"] * CS + 9
              pyxel.circ(bx, by, 5, 13)
              pyxel.pset(bx - 2, by - 2, 7)
        self.draw_villain()

        if self.mode != "edit":
            for p in self.fx:
                pyxel.pset(p[0], p[1], 10 if p[4] % 2 else 7)
            for s, x, y, col, _ in self.texts:
                pyxel.text(x + 1, y + 1, s, 0)
                pyxel.text(x, y, s, col)
            # HP / 情報
            pyxel.text(4, 174, "HP", 8)
            pyxel.rect(16, 174, 100, 5, 5)
            pyxel.rect(16, 174, max(0, self.v["hp"]) * 100 // STAGE["hp"], 5, 8)
            pyxel.text(4, 184, "AGONY %d  COMBO %d  TIME %d" % (self.agony_steps, self.combo,
                                                              MAX_STEPS - self.steps), 7)
            pyxel.text(130, 174, "BALL %d" % (self.balls_left + (1 if self.ball else 0)), 13)
            pyxel.text(160, 192, "R: back to edit", 5)
        else:
            for i, (p, name, _) in enumerate(PARTS):
                px = 4 + i * 32
                if p == self.sel:
                    pyxel.rectb(px - 1, 173, 31, 26, 10)
                self.draw_part(p, px + 7, 174)
                pyxel.text(px, 192, "%s %d" % (name[:4], self.stock[p]), 7 if self.stock[p] else 5)
            pyxel.rect(170, 174, 66, 12, 8)
            pyxel.text(186, 177, "START", 7)
            pyxel.rect(170, 188, 66, 10, 5)
            pyxel.text(190, 190, "CLEAR", 7)
            pyxel.text(130, 3, "BEST %d" % self.best, 10)

        if self.mode == "result":
            pyxel.rect(40, 50, 160, 92, 0)
            pyxel.rectb(40, 50, 160, 92, 7)
            title = "PARDONED... (x0.3)" if self.pardoned else "EXECUTION COMPLETE"
            pyxel.text(120 - len(title) * 2, 56, title, 9 if self.pardoned else 8)
            pyxel.text(52, 72, "HIT POINTS   %6d" % self.hit_pts, 7)
            pyxel.text(52, 82, "AGONY BONUS  %6d" % self.agony_pts, 7)
            pyxel.text(52, 92, "MAX COMBO    %6d" % self.max_combo, 7)
            pyxel.text(52, 108, "AGONY SCORE  %6d" % self.total, 10)
            if self.new_best:
                pyxel.text(150, 108, "NEW!", 14)
            pyxel.text(66, 128, "click: back to edit", 5)


if __name__ == "__main__":
    Game()
