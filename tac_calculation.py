LEFT_ASSOC = 0
RIGHT_ASSOC = 1

PRIORITY = 0
ASSOCIATIVITY = 1

OPERATORS = {
    '!'  : (3, RIGHT_ASSOC),
    '*'  : (5, LEFT_ASSOC),
    '/'  : (5, LEFT_ASSOC),
    '%'  : (5, LEFT_ASSOC),
    '+'  : (6, LEFT_ASSOC),
    '-'  : (6, LEFT_ASSOC),
    '<'  : (8, LEFT_ASSOC),
    '<=' : (8, LEFT_ASSOC),
    '>'  : (8, LEFT_ASSOC),
    '>=' : (8, LEFT_ASSOC),
    '==' : (9, LEFT_ASSOC),
    '!=' : (9, LEFT_ASSOC),
    '&'  : (13, LEFT_ASSOC),
    '|'  : (14, LEFT_ASSOC)
}



#
#  Calculation error
#
class CalculationError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class Calculator:
    def __init__(self, tokens):
        self.rpn_tokens = []
        self.infix_to_rpn(tokens)
        self.multiport = False
        # convert tokens into postfix notation (aka RPN)

    @staticmethod
    def is_operator(token):
        return token.name in OPERATORS.keys()

    def is_associative(self, token, assoc):
        if not self.is_operator(token):
            raise CalculationError('Invalid token: %s' % token)
        return OPERATORS[token.name][ASSOCIATIVITY] == assoc

    def cmp_precedence(self, token1, token2):
        if not self.is_operator(token1) or not self.is_operator(token2):
            raise CalculationError('Invalid tokens: %s %s' % (token1, token2))
        return OPERATORS[token2.name][PRIORITY] - OPERATORS[token1.name][PRIORITY]

    def infix_to_rpn(self, tokens):
        stack = []
        for token in tokens:
            if self.is_operator(token):
                while len(stack) != 0 and self.is_operator(stack[-1]):
                    if ((self.is_associative(token, LEFT_ASSOC) and self.cmp_precedence(token, stack[-1]) <= 0) or
                            (self.is_associative(token, RIGHT_ASSOC) and self.cmp_precedence(token, stack[-1]) < 0)):
                        self.rpn_tokens.append(stack.pop())
                        continue
                    break
                stack.append(token)
            elif token.value == '(':
                stack.append(token)
            elif token.value == ')':
                while len(stack) != 0 and stack[-1].value != '(':
                    self.rpn_tokens.append(stack.pop())
                stack.pop()
            else:
                self.rpn_tokens.append(token)
        while len(stack) != 0:
            self.rpn_tokens.append(stack.pop())

    @staticmethod
    def value(token, variables):
        if token.name == 'var':
            if token.value in variables:
                v = variables.get(token.value, (0.0, None))  # treat undefined variables as 0.0
            else:
                return -1
            if v is None:
                return 0.0
            return float(v)
        else:
            raise CalculationError('Bad token: %s' % token)

    @staticmethod
    def unary_op(op, a):
        if op == '!':
            return not a
        else:
            raise CalculationError('Bad operator: %s' % op)

    @staticmethod
    def binary_op(op, a, b):
        if op == '*':
            return a * b
        elif op == '/':
            if b == 0.0:
                raise CalculationError('Division by zero')
            return a / b
        elif op == '%':
            return a % b
        elif op == '+':
            return a + b
        elif op == '-':
            return a - b
        elif op == '<':
            return a < b
        elif op == '<=':
            return a <= b
        elif op == '>':
            return a > b
        elif op == '>=':
            return a >= b
        elif op == '==':
            return a == b
        elif op == '!=':
            return a != b
        elif op == '&':
            return a and b
        elif op == '|':
            return a or b
        else:
            raise CalculationError('Bad operator: %s' % op)

    def calculate(self, values, multiport):
        """Execute the operation against rpn_tokens"""
        # if multiple logical ports are evaluated in expression
        stack = []
        if multiport > 1:
            msg = ''
            for token in self.rpn_tokens:
                if token.name == 'var':
                    for port_values in values.iteritems():
                        val = self.value(token, port_values[1])
                        if val != -1:
                            stack.append(val)
                            msg += str(token.value) + '=' + str(val) + ' '
                            break
                elif token.name == 'num':
                    stack.append(float(token.value))
                else:
                    if token.name == 'not':
                        stack.append(self.unary_op(token.name, stack.pop()))
                    else:
                        if len(stack) > 1:
                            b = stack.pop()
                            a = stack.pop()
                            op_result = self.binary_op(token.name, a, b)
                            stack.append(op_result)

        # if the expression compares values within one and the same port
        else:
            for port_values in values.iteritems():
                msg = ''
                stack = []
                if multiport == 0:
                    msg = port_values[0].kind[0] + 'port' + str(port_values[0].number) + ': '
                for token in self.rpn_tokens:
                    if token.name == 'var':
                        val = self.value(token, port_values[1])
                        stack.append(val)
                        msg += str(token.value) + '=' + str(val) + ' '

                    elif token.name == 'num':
                        stack.append(float(token.value))
                    else:
                        if token.name == 'not':
                            stack.append(self.unary_op(token.name, stack.pop()))
                        else:
                            b = stack.pop()
                            a = stack.pop()
                            op_result = self.binary_op(token.name, a, b)
                            stack.append(op_result)
                if not op_result:
                    break
        result = stack.pop()
        # print ("RETURN: " + str (result))
        return result, msg
