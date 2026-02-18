document.addEventListener("DOMContentLoaded", function () {

    const senhaInput = document.getElementById("senha");
    const toggleSenha = document.getElementById("toggleSenha");
    const msgSenha = document.getElementById("msg-senha");

    if (senhaInput && toggleSenha && msgSenha) {
        senhaInput.addEventListener("input", () => {
            if (senhaInput.value.length === 0) {
                toggleSenha.style.display = "none";
                senhaInput.type = "password";
                toggleSenha.classList.remove("ativo");
                msgSenha.className = "msg-senha";
                msgSenha.textContent = "";
                return;
            }
            toggleSenha.style.display = "block";
        });

        toggleSenha.addEventListener("click", () => {
            const mostrar = senhaInput.type === "password";
            senhaInput.type = mostrar ? "text" : "password";
            toggleSenha.classList.toggle("ativo", mostrar);
        });

        senhaInput.addEventListener("input", () => {
            const senha = senhaInput.value;

            if (senha.length < 5) {
                msgSenha.textContent = "A senha deve ter no mínimo 5 caracteres";
                msgSenha.className = "msg-senha msg-vermelha visivel";
                return;
            }

            if (!/[A-Z]/.test(senha) || !/[a-z]/.test(senha)) {
                msgSenha.textContent = "Use maiúscula e minúscula";
                msgSenha.className = "msg-senha msg-amarela visivel";
                return;
            }

            msgSenha.textContent = "Senha válida";
            msgSenha.className = "msg-senha msg-verde visivel";
        });
    }

    function ativarOlho(inputId, toggleId) {
        const input = document.getElementById(inputId);
        const toggle = document.getElementById(toggleId);

        if (!input || !toggle) return;

        input.addEventListener("input", () => {
            toggle.style.display = input.value ? "block" : "none";
        });

        toggle.addEventListener("click", () => {
            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            toggle.classList.toggle("ativo", isPassword);
        });
    }

    ativarOlho("senha-login", "toggle-login");
    ativarOlho("confirmar", "toggleConfirmar");

    const confirmarInput = document.getElementById("confirmar");

    if (senhaInput && confirmarInput) {
        confirmarInput.addEventListener("input", () => {
            if (confirmarInput.value !== senhaInput.value) {
                confirmarInput.setCustomValidity("As senhas não conferem");
            } else {
                confirmarInput.setCustomValidity("");
            }
        });
    }

const toggle = document.getElementById("menu-toggle");
const navMenu = document.getElementById("nav-menu");
const overlay = document.getElementById("menu-overlay");

function fecharMenu() {
    navMenu.classList.remove("active");
    overlay.classList.remove("active");
    overlay.style.display = "none";
}

if (toggle && navMenu && overlay) {
    toggle.addEventListener("click", () => {
        const ativo = navMenu.classList.toggle("active");
        overlay.classList.toggle("active");
        overlay.style.display = ativo ? "block" : "none";
    });

    overlay.addEventListener("click", fecharMenu);

    // 🔹 fecha ao clicar em links
    document.querySelectorAll("#nav-menu a").forEach(link => {
        link.addEventListener("click", fecharMenu);
    });

    // 🔹 fecha ao voltar no histórico (botão do celular)
    window.addEventListener("pageshow", fecharMenu);
    window.addEventListener("popstate", fecharMenu);
}



});
