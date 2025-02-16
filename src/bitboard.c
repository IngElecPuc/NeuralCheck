#include "bitboard.h"

void visualize(int64_t bitboard)
{
    uint64_t unum = (uint64_t) bitboard; // Conversion to uint64_t to handle unsigned bits.
    int bits = sizeof(unum) * 8; // 64 bits

    for (int i = bits - 1; i >= 0; i--) 
    {    
        putchar((unum & (1ULL << i)) ? '1' : '0'); // Prints '1' or '0' depending on whether bit i is active
        if (i % 8 == 0)
            putchar('\n');
    }
    putchar('\n');
}

int64_t getBitboardPosition(const char *position)
{
    char cols2int[] = "hgfedcba";
    char rows2int[] = "12345678";
    int col, row;
    for (col = 0; col < 8; col++)
        if (cols2int[col] == position[0])
            break;

    for (row = 0; row < 8; row++)
        if (rows2int[row] == position[1])
            break;
    
    return (1LL << col) << (row * 8);
}

