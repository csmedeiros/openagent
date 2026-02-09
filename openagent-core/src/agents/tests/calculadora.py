#!/usr/bin/env python3
"""
Calculadora Simples em CLI
Autor: OpenAgent
Descrição: Uma calculadora de linha de comando com operações básicas
"""

def soma(a, b):
    """Soma dois números"""
    return a + b

def subtracao(a, b):
    """Subtrai dois números"""
    return a - b

def multiplicacao(a, b):
    """Multiplica dois números"""
    return a * b

def divisao(a, b):
    """Divide dois números"""
    if b == 0:
        raise ValueError("Não é possível dividir por zero!")
    return a / b

def exibir_menu():
    """Exibe o menu de opções"""
    print("\n" + "="*30)
    print("      CALCULADORA SIMPLES")
    print("="*30)
    print("1. Soma (+)")
    print("2. Subtração (-)")
    print("3. Multiplicação (*)")
    print("4. Divisão (/)")
    print("5. Sair")
    print("="*30)

def obter_numero(mensagem):
    """Obtém um número válido do usuário"""
    while True:
        try:
            return float(input(mensagem))
        except ValueError:
            print("❌ Por favor, digite um número válido!")

def calcular(operacao, num1, num2):
    """Realiza o cálculo baseado na operação escolhida"""
    operacoes = {
        1: (soma, "+"),
        2: (subtracao, "-"),
        3: (multiplicacao, "*"),
        4: (divisao, "/")
    }
    
    if operacao in operacoes:
        funcao, simbolo = operacoes[operacao]
        resultado = funcao(num1, num2)
        print(f"\n✅ Resultado: {num1} {simbolo} {num2} = {resultado}")
        return resultado
    else:
        raise ValueError("Operação inválida!")

def main():
    """Função principal da calculadora"""
    print("🧮 Bem-vindo à Calculadora Simples!")
    
    while True:
        try:
            exibir_menu()
            
            # Obter escolha do usuário
            while True:
                try:
                    escolha = int(input("\nEscolha uma operação (1-5): "))
                    if 1 <= escolha <= 5:
                        break
                    else:
                        print("❌ Por favor, escolha um número entre 1 e 5!")
                except ValueError:
                    print("❌ Por favor, digite um número válido!")
            
            # Sair do programa
            if escolha == 5:
                print("\n👋 Obrigado por usar a calculadora! Até logo!")
                break
            
            # Obter números
            print(f"\n📝 Operação escolhida: {escolha}")
            num1 = obter_numero("Digite o primeiro número: ")
            num2 = obter_numero("Digite o segundo número: ")
            
            # Realizar cálculo
            calcular(escolha, num1, num2)
            
            # Perguntar se deseja continuar
            input("\nPressione ENTER para continuar...")
            
        except ValueError as e:
            print(f"❌ Erro: {e}")
            input("\nPressione ENTER para continuar...")
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            input("\nPressione ENTER para continuar...")

if __name__ == "__main__":
    main()