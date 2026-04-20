/* ═══════════════════════════════════════════════════════
   3D Cricket Ground Animation - Match Detail Page
   ═══════════════════════════════════════════════════════ */

class CricketGroundAnimation {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.width = this.canvas.width;
        this.height = this.canvas.height;
        
        this.ball = { x: 50, y: 50, radius: 8, vx: 2, vy: 1 };
        this.particles = [];
        this.crowd = this.initCrowd();
        this.animate();
    }

    initCrowd() {
        const crowd = [];
        for (let i = 0; i < 100; i++) {
            crowd.push({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                color: `hsl(${Math.random() * 60}, 100%, ${40 + Math.random() * 20}%)`,
                wave: Math.random() * Math.PI * 2,
            });
        }
        return crowd;
    }

    drawGround() {
        // Oval background
        this.ctx.fillStyle = '#1b5e20';
        this.ctx.fillRect(0, 0, this.width, this.height);

        // Mowing pattern
        for (let i = 0; i < this.height; i += 20) {
            this.ctx.fillStyle = i % 40 === 0 ? '#2e7d32' : '#1b5e20';
            this.ctx.fillRect(0, i, this.width, 20);
        }

        // Oval boundary
        this.ctx.strokeStyle = '#fff';
        this.ctx.lineWidth = 3;
        this.ctx.beginPath();
        this.ctx.ellipse(this.width / 2, this.height / 2, this.width / 2 - 20, this.height / 2 - 20, 0, 0, Math.PI * 2);
        this.ctx.stroke();

        // 30-yard circle
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.ellipse(this.width / 2, this.height / 2, 120, 100, 0, 0, Math.PI * 2);
        this.ctx.stroke();

        // Pitch (center rectangle)
        this.ctx.strokeStyle = '#fff';
        this.ctx.lineWidth = 2;
        this.ctx.strokeRect(this.width / 2 - 30, this.height / 2 - 100, 60, 200);

        // Stumps
        this.drawStumps(this.width / 2, this.height / 2 - 100);
        this.drawStumps(this.width / 2, this.height / 2 + 100);

        // Crease lines
        this.ctx.strokeStyle = '#fff';
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([5, 5]);
        this.ctx.beginPath();
        this.ctx.moveTo(this.width / 2 - 50, this.height / 2 - 105);
        this.ctx.lineTo(this.width / 2 + 50, this.height / 2 - 105);
        this.ctx.stroke();
        this.ctx.setLineDash([]);
    }

    drawStumps(x, y) {
        // Stump poles
        this.ctx.fillStyle = '#fff';
        for (let i = 0; i < 3; i++) {
            this.ctx.fillRect(x - 12 + i * 12, y - 30, 4, 30);
        }
        // Bails
        this.ctx.fillRect(x - 15, y - 5, 30, 2);
    }

    drawCrowd() {
        this.crowd.forEach((person, i) => {
            person.wave += 0.05;
            const wobble = Math.sin(person.wave) * 3;

            this.ctx.fillStyle = person.color;
            this.ctx.globalAlpha = 0.6;
            this.ctx.fillRect(person.x + wobble, person.y + wobble, 4, 6);
            this.ctx.globalAlpha = 1;
        });
    }

    drawBall() {
        // Ball shadow
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.2)';
        this.ctx.beginPath();
        this.ctx.ellipse(this.ball.x, this.ball.y + 150, 15, 5, 0, 0, Math.PI * 2);
        this.ctx.fill();

        // Ball
        this.ctx.fillStyle = '#ff6b6b';
        this.ctx.beginPath();
        this.ctx.arc(this.ball.x, this.ball.y, this.ball.radius, 0, Math.PI * 2);
        this.ctx.fill();

        // Ball shine
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        this.ctx.beginPath();
        this.ctx.arc(this.ball.x - 2, this.ball.y - 2, 3, 0, Math.PI * 2);
        this.ctx.fill();

        // Trajectory line
        if (this.ball.vx || this.ball.vy) {
            this.ctx.strokeStyle = 'rgba(255, 107, 107, 0.3)';
            this.ctx.setLineDash([2, 4]);
            this.ctx.beginPath();
            this.ctx.moveTo(this.ball.x, this.ball.y);
            this.ctx.lineTo(this.ball.x + this.ball.vx * 20, this.ball.y + this.ball.vy * 20);
            this.ctx.stroke();
            this.ctx.setLineDash([]);
        }
    }

    drawParticles() {
        this.particles = this.particles.filter(p => p.life > 0);

        this.particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.life--;

            this.ctx.fillStyle = p.color;
            this.ctx.globalAlpha = p.life / p.maxLife;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            this.ctx.fill();
            this.ctx.globalAlpha = 1;
        });
    }

    updateBall() {
        this.ball.x += this.ball.vx;
        this.ball.y += this.ball.vy;
        this.ball.vy += 0.3; // Gravity

        // Bounce
        if (this.ball.y > this.height - this.ball.radius) {
            this.ball.y = this.height - this.ball.radius;
            this.ball.vy *= -0.8;
            this.ball.vx *= 0.9;

            // Create particles on bounce
            this.createBurstParticles(this.ball.x, this.ball.y, 8, '#90ee90');
        }

        // Reset if out of bounds
        if (this.ball.y > this.height + 50 || this.ball.x < -50 || this.ball.x > this.width + 50) {
            this.resetBall();
        }
    }

    createBurstParticles(x, y, count, color) {
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count;
            this.particles.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * 3,
                vy: Math.sin(angle) * 3,
                color: color,
                radius: 3,
                life: 20,
                maxLife: 20,
            });
        }
    }

    resetBall() {
        this.ball = {
            x: this.width / 2 + (Math.random() - 0.5) * 100,
            y: 50,
            radius: 8,
            vx: (Math.random() - 0.5) * 6,
            vy: Math.random() * 2 + 1,
        };
    }

    drawScore() {
        const score = document.querySelector('[data-score]')?.textContent || '45/3';
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        this.ctx.fillRect(10, 10, 150, 60);

        this.ctx.fillStyle = '#ffd700';
        this.ctx.font = 'bold 24px Arial';
        this.ctx.fillText('Score: ' + score, 20, 40);
        this.ctx.font = '14px Arial';
        this.ctx.fillStyle = '#fff';
        this.ctx.fillText('Overs: 12.3/20', 20, 60);
    }

    animate = () => {
        this.drawGround();
        this.drawCrowd();
        this.updateBall();
        this.drawBall();
        this.drawParticles();
        this.drawScore();

        requestAnimationFrame(this.animate);
    };
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('cricket-canvas')) {
        new CricketGroundAnimation('cricket-canvas');
    }
});
